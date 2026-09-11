"""Integration tests for Simple Bookings — spaces, dated slots, book/waitlist/cancel."""

from datetime import date, timedelta

import pytest

from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


@pytest.fixture(autouse=True)
def _no_broker(monkeypatch):
    """Keep the endpoint off the Celery broker — email dispatch is unit-tested
    separately, and a real ``.delay()`` blocks on an unavailable broker."""
    import app.api.v1.endpoints.bookings as ep
    from app.domains.bookings.notifications import NullBookingNotifier

    monkeypatch.setattr(ep, "_notifier", NullBookingNotifier())


def _auth(user):
    from app.core.security.jwt import create_access_token

    return {"access_token": create_access_token(user.id)}


def _org(db, *, enabled=True, **features):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(
            id=1, name="Test Club", locale="es", timezone="Europe/Madrid",
            currency="EUR", date_format="DD/MM/YYYY",
        )
        db.add(org)
    org.features = {"bookings": True, **features} if enabled else {}
    db.flush()
    return org


def _user(db, role="admin", email=None):
    email = email or f"{role}-bk@examplee6e3b1.com"
    person = Person(first_name=role.title(), last_name="Tester", email=email)
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id, email=email,
        password_hash=hash_password("password123"), role=role, is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _member_user(db, email, membership_type=None):
    person = Person(first_name="Mem", last_name="Ber", email=email)
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id, email=email,
        password_hash=hash_password("password123"), role="member", is_active=True,
    )
    db.add(user)
    db.flush()
    member = Member(
        person_id=person.id, user_id=user.id, status="active", is_active=True,
        membership_type_id=membership_type.id if membership_type else None,
    )
    db.add(member)
    db.flush()
    return user, member


def _membership_type(db, slug):
    mt = MembershipType(name=slug.title(), slug=slug, is_active=True)
    db.add(mt)
    db.flush()
    return mt


def _future(days=3):
    return date.today() + timedelta(days=days)


def _make_space(client, admin, *, open_="08:00:00", close="22:00:00", allowed=None):
    body = {"name": "Court 1", "open_time": open_, "close_time": close}
    if allowed is not None:
        body["allowed_membership_types"] = allowed
    sp = client.post("/api/v1/spaces", json=body, cookies=_auth(admin))
    assert sp.status_code == 201, sp.text
    return sp.json()["id"]


def _make_space_and_slot(client, admin, *, capacity=1, on=None, allowed=None):
    on = on or _future(3)
    space_id = _make_space(client, admin, allowed=allowed)
    sl = client.post(
        f"/api/v1/spaces/{space_id}/slots",
        json={
            "slot_date": on.isoformat(), "start_time": "10:00:00",
            "end_time": "11:00:00", "capacity": capacity,
        },
        cookies=_auth(admin),
    )
    assert sl.status_code == 201, sl.text
    return space_id, sl.json()[0]["id"]


class TestFeatureGate:
    def test_spaces_404_when_disabled(self, client, db):
        _org(db, enabled=False)
        admin = _user(db, "admin")
        r = client.get("/api/v1/spaces", cookies=_auth(admin))
        assert r.status_code == 404

    def test_booking_404_when_disabled(self, client, db):
        _org(db, enabled=False)
        user, _ = _member_user(db, "m404@examplee6e3b1.com")
        r = client.post(
            "/api/v1/bookings",
            json={"space_slot_id": 1},
            cookies=_auth(user),
        )
        assert r.status_code == 404


class TestSpacesRBAC:
    def test_admin_creates_space(self, client, db):
        _org(db)
        admin = _user(db, "admin")
        r = client.post(
            "/api/v1/spaces",
            json={"name": "Pitch", "open_time": "08:00:00", "close_time": "22:00:00"},
            cookies=_auth(admin),
        )
        assert r.status_code == 201
        assert r.json()["name"] == "Pitch"

    def test_member_cannot_create_space(self, client, db):
        _org(db)
        user, _ = _member_user(db, "m-nope@examplee6e3b1.com")
        r = client.post(
            "/api/v1/spaces",
            json={"name": "Pitch", "open_time": "08:00:00", "close_time": "22:00:00"},
            cookies=_auth(user),
        )
        assert r.status_code == 403

    def test_slot_outside_hours_rejected(self, client, db):
        _org(db)
        admin = _user(db, "admin")
        space_id = _make_space(client, admin, open_="10:00:00", close="12:00:00")
        r = client.post(
            f"/api/v1/spaces/{space_id}/slots",
            json={
                "slot_date": _future(3).isoformat(),
                "start_time": "09:00:00", "end_time": "10:00:00", "capacity": 1,
            },
            cookies=_auth(admin),
        )
        assert r.status_code == 422


class TestSlots:
    def test_past_slot_rejected(self, client, db):
        _org(db)
        admin = _user(db, "admin")
        space_id = _make_space(client, admin)
        r = client.post(
            f"/api/v1/spaces/{space_id}/slots",
            json={
                "slot_date": (date.today() - timedelta(days=1)).isoformat(),
                "start_time": "10:00:00", "end_time": "11:00:00",
            },
            cookies=_auth(admin),
        )
        assert r.status_code == 422

    def test_repeat_creates_series(self, client, db):
        _org(db)
        admin = _user(db, "admin")
        space_id = _make_space(client, admin)
        start = _future(7)
        r = client.post(
            f"/api/v1/spaces/{space_id}/slots",
            json={
                "slot_date": start.isoformat(),
                "start_time": "10:00:00", "end_time": "11:00:00",
                "repeat": {"weekdays": [start.weekday()], "interval_weeks": 1, "count": 3},
            },
            cookies=_auth(admin),
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert len(body) == 3
        assert len({s["series_id"] for s in body}) == 1
        assert body[0]["series_id"] is not None
        assert body[0]["series_size_upcoming"] == 3
        assert body[2]["series_size_upcoming"] == 1

    def test_all_day_slot_spans_opening_hours(self, client, db):
        _org(db)
        admin = _user(db, "admin")
        space_id = _make_space(client, admin, open_="09:00:00", close="21:00:00")
        r = client.post(
            f"/api/v1/spaces/{space_id}/slots",
            json={"slot_date": _future(3).isoformat(), "all_day": True},
            cookies=_auth(admin),
        )
        assert r.status_code == 201, r.text
        slot = r.json()[0]
        assert slot["start_time"] == "09:00:00"
        assert slot["end_time"] == "21:00:00"

    def test_update_apply_to_upcoming(self, client, db):
        _org(db)
        admin = _user(db, "admin")
        space_id = _make_space(client, admin)
        start = _future(7)
        r = client.post(
            f"/api/v1/spaces/{space_id}/slots",
            json={
                "slot_date": start.isoformat(),
                "start_time": "10:00:00", "end_time": "11:00:00",
                "repeat": {"weekdays": [start.weekday()], "interval_weeks": 1, "count": 3},
            },
            cookies=_auth(admin),
        )
        slots = r.json()
        ru = client.put(
            f"/api/v1/spaces/{space_id}/slots/{slots[1]['id']}?apply_to=upcoming",
            json={"capacity": 5},
            cookies=_auth(admin),
        )
        assert ru.status_code == 200, ru.text
        listed = client.get(
            f"/api/v1/spaces/{space_id}/slots", cookies=_auth(admin)
        ).json()
        by_id = {s["id"]: s for s in listed}
        assert by_id[slots[0]["id"]]["capacity"] == 1
        assert by_id[slots[1]["id"]]["capacity"] == 5
        assert by_id[slots[2]["id"]]["capacity"] == 5


class TestDeleteGuards:
    def test_slot_delete_409_then_force(self, client, db):
        _org(db)
        admin = _user(db, "admin")
        space_id, slot_id = _make_space_and_slot(client, admin, capacity=2)
        u1, _ = _member_user(db, "d1@examplee6e3b1.com")
        u2, _ = _member_user(db, "d2@examplee6e3b1.com")
        for u in (u1, u2):
            client.post(
                "/api/v1/bookings", json={"space_slot_id": slot_id}, cookies=_auth(u)
            )

        r = client.delete(
            f"/api/v1/spaces/{space_id}/slots/{slot_id}", cookies=_auth(admin)
        )
        assert r.status_code == 409
        assert r.json()["detail"]["affected_members"] == 2

        rf = client.delete(
            f"/api/v1/spaces/{space_id}/slots/{slot_id}?force=true",
            cookies=_auth(admin),
        )
        assert rf.status_code == 204
        listed = client.get(
            f"/api/v1/spaces/{space_id}/slots", cookies=_auth(admin)
        ).json()
        assert listed == []

    def test_slot_delete_without_bookings_needs_no_force(self, client, db):
        _org(db)
        admin = _user(db, "admin")
        space_id, slot_id = _make_space_and_slot(client, admin)
        r = client.delete(
            f"/api/v1/spaces/{space_id}/slots/{slot_id}", cookies=_auth(admin)
        )
        assert r.status_code == 204

    def test_space_delete_409_then_force(self, client, db):
        _org(db)
        admin = _user(db, "admin")
        space_id, slot_id = _make_space_and_slot(client, admin)
        u1, _ = _member_user(db, "d3@examplee6e3b1.com")
        client.post(
            "/api/v1/bookings", json={"space_slot_id": slot_id}, cookies=_auth(u1)
        )

        r = client.delete(f"/api/v1/spaces/{space_id}", cookies=_auth(admin))
        assert r.status_code == 409
        assert r.json()["detail"]["affected_members"] == 1

        rf = client.delete(
            f"/api/v1/spaces/{space_id}?force=true", cookies=_auth(admin)
        )
        assert rf.status_code == 204
        assert (
            client.get(f"/api/v1/spaces/{space_id}", cookies=_auth(admin)).status_code
            == 404
        )


    def test_space_hours_narrowing_409_then_force(self, client, db):
        _org(db)
        admin = _user(db, "admin")
        space_id, slot_id = _make_space_and_slot(client, admin)  # 10:00-11:00
        u1, _ = _member_user(db, "h1@examplee6e3b1.com")
        client.post(
            "/api/v1/bookings", json={"space_slot_id": slot_id}, cookies=_auth(u1)
        )

        r = client.put(
            f"/api/v1/spaces/{space_id}",
            json={"open_time": "12:00:00"},
            cookies=_auth(admin),
        )
        assert r.status_code == 409
        assert r.json()["detail"] == {"slots_outside_hours": 1, "affected_members": 1}

        rf = client.put(
            f"/api/v1/spaces/{space_id}?force=true",
            json={"open_time": "12:00:00"},
            cookies=_auth(admin),
        )
        assert rf.status_code == 200
        assert rf.json()["open_time"] == "12:00:00"
        slots = client.get(f"/api/v1/spaces/{space_id}/slots", cookies=_auth(admin)).json()
        assert slots == []


class TestBooking:
    def test_member_books_a_free_slot(self, client, db):
        _org(db)
        admin = _user(db, "admin")
        _space_id, slot_id = _make_space_and_slot(client, admin)
        user, _ = _member_user(db, "booker@examplee6e3b1.com")

        r = client.post(
            "/api/v1/bookings",
            json={"space_slot_id": slot_id},
            cookies=_auth(user),
        )
        assert r.status_code == 201, r.text
        assert r.json()["status"] == "booked"

    def test_second_member_waitlisted_then_double_book_conflicts(self, client, db):
        _org(db)
        admin = _user(db, "admin")
        _space_id, slot_id = _make_space_and_slot(client, admin, capacity=1)
        u1, _ = _member_user(db, "b1@examplee6e3b1.com")
        u2, _ = _member_user(db, "b2@examplee6e3b1.com")

        r1 = client.post(
            "/api/v1/bookings",
            json={"space_slot_id": slot_id},
            cookies=_auth(u1),
        )
        assert r1.json()["status"] == "booked"

        r2 = client.post(
            "/api/v1/bookings",
            json={"space_slot_id": slot_id},
            cookies=_auth(u2),
        )
        assert r2.json()["status"] == "waitlisted"

        # u1 booking again → duplicate → 409
        rdup = client.post(
            "/api/v1/bookings",
            json={"space_slot_id": slot_id},
            cookies=_auth(u1),
        )
        assert rdup.status_code == 409

    def test_full_slot_conflicts_when_waitlist_disabled(self, client, db):
        _org(db, booking_waitlist_enabled=False)
        admin = _user(db, "admin")
        _space_id, slot_id = _make_space_and_slot(client, admin, capacity=1)
        u1, _ = _member_user(db, "f1@examplee6e3b1.com")
        u2, _ = _member_user(db, "f2@examplee6e3b1.com")

        client.post(
            "/api/v1/bookings",
            json={"space_slot_id": slot_id},
            cookies=_auth(u1),
        )
        r2 = client.post(
            "/api/v1/bookings",
            json={"space_slot_id": slot_id},
            cookies=_auth(u2),
        )
        assert r2.status_code == 409

    def test_cancel_promotes_waitlisted_member(self, client, db):
        _org(db, booking_cancellation_deadline_hours=0)
        admin = _user(db, "admin")
        _space_id, slot_id = _make_space_and_slot(client, admin, capacity=1)
        u1, _ = _member_user(db, "c1@examplee6e3b1.com")
        u2, m2 = _member_user(db, "c2@examplee6e3b1.com")

        r1 = client.post(
            "/api/v1/bookings",
            json={"space_slot_id": slot_id},
            cookies=_auth(u1),
        )
        booking1_id = r1.json()["id"]
        client.post(
            "/api/v1/bookings",
            json={"space_slot_id": slot_id},
            cookies=_auth(u2),
        )

        rc = client.delete(f"/api/v1/bookings/{booking1_id}", cookies=_auth(u1))
        assert rc.status_code == 204

        mine = client.get("/api/v1/me/bookings?scope=upcoming", cookies=_auth(u2))
        assert mine.status_code == 200
        assert mine.json()[0]["status"] == "booked"

    def test_my_bookings_reports_occupancy(self, client, db):
        _org(db)
        admin = _user(db, "admin")
        _space_id, slot_id = _make_space_and_slot(client, admin, capacity=3)
        u1, _ = _member_user(db, "occ1@examplee6e3b1.com")
        u2, _ = _member_user(db, "occ2@examplee6e3b1.com")
        client.post(
            "/api/v1/bookings", json={"space_slot_id": slot_id}, cookies=_auth(u1)
        )
        client.post(
            "/api/v1/bookings", json={"space_slot_id": slot_id}, cookies=_auth(u2)
        )

        mine = client.get("/api/v1/me/bookings?scope=upcoming", cookies=_auth(u1))
        assert mine.status_code == 200
        row = mine.json()[0]
        assert row["capacity"] == 3
        assert row["booked_count"] == 2
        assert row["slot_date"] == _future(3).isoformat()

    def test_member_cannot_cancel_others_booking(self, client, db):
        _org(db, booking_cancellation_deadline_hours=0)
        admin = _user(db, "admin")
        _space_id, slot_id = _make_space_and_slot(client, admin, capacity=1)
        u1, _ = _member_user(db, "own1@examplee6e3b1.com")
        u2, _ = _member_user(db, "own2@examplee6e3b1.com")

        r1 = client.post(
            "/api/v1/bookings",
            json={"space_slot_id": slot_id},
            cookies=_auth(u1),
        )
        booking_id = r1.json()["id"]
        r = client.delete(f"/api/v1/bookings/{booking_id}", cookies=_auth(u2))
        assert r.status_code == 403


class TestAdminBookingsView:
    def test_admin_lists_space_bookings(self, client, db):
        _org(db)
        admin = _user(db, "admin")
        space_id, slot_id = _make_space_and_slot(client, admin, capacity=2)
        u1, _ = _member_user(db, "a1@examplee6e3b1.com")
        client.post(
            "/api/v1/bookings",
            json={"space_slot_id": slot_id},
            cookies=_auth(u1),
        )
        r = client.get(f"/api/v1/spaces/{space_id}/bookings", cookies=_auth(admin))
        assert r.status_code == 200
        body = r.json()
        assert body["meta"]["total"] == 1
        assert body["items"][0]["member_name"]
        assert body["items"][0]["slot_date"] == _future(3).isoformat()


class TestMembershipGating:
    """A space restricted to membership types refuses the wrong tier, and says
    which of the two things went wrong."""

    def test_admin_sets_and_clears_the_allow_list(self, client, db):
        _org(db)
        admin = _user(db, "admin")
        premium = _membership_type(db, "premium-gate")
        space_id = _make_space(client, admin, allowed=[premium.id])

        r = client.get(f"/api/v1/spaces/{space_id}", cookies=_auth(admin))
        assert r.json()["allowed_membership_types"] == [premium.id]

        r = client.put(
            f"/api/v1/spaces/{space_id}",
            json={"allowed_membership_types": []},
            cookies=_auth(admin),
        )
        assert r.status_code == 200, r.text
        assert r.json()["allowed_membership_types"] is None

    def test_allowed_member_books(self, client, db):
        _org(db)
        admin = _user(db, "admin")
        premium = _membership_type(db, "premium-books")
        _space_id, slot_id = _make_space_and_slot(
            client, admin, allowed=[premium.id]
        )
        user, _ = _member_user(db, "ok@examplee6e3b1.com", membership_type=premium)

        r = client.post(
            "/api/v1/bookings",
            json={"space_slot_id": slot_id},
            cookies=_auth(user),
        )
        assert r.status_code == 201, r.text
        assert r.json()["status"] == "booked"

    def test_member_on_another_tier_is_forbidden(self, client, db):
        _org(db)
        admin = _user(db, "admin")
        premium = _membership_type(db, "premium-blocks")
        basic = _membership_type(db, "basic-blocked")
        _space_id, slot_id = _make_space_and_slot(
            client, admin, allowed=[premium.id]
        )
        user, _ = _member_user(db, "no@examplee6e3b1.com", membership_type=basic)

        r = client.post(
            "/api/v1/bookings",
            json={"space_slot_id": slot_id},
            cookies=_auth(user),
        )
        assert r.status_code == 403
        assert "membership type does not include" in r.json()["detail"]

    def test_member_with_no_tier_is_told_something_else(self, client, db):
        _org(db)
        admin = _user(db, "admin")
        premium = _membership_type(db, "premium-untyped")
        _space_id, slot_id = _make_space_and_slot(
            client, admin, allowed=[premium.id]
        )
        user, _ = _member_user(db, "none@examplee6e3b1.com")

        r = client.post(
            "/api/v1/bookings",
            json={"space_slot_id": slot_id},
            cookies=_auth(user),
        )
        assert r.status_code == 403
        assert "no membership type assigned" in r.json()["detail"]

    def test_availability_reports_the_restriction(self, client, db):
        _org(db)
        admin = _user(db, "admin")
        premium = _membership_type(db, "premium-avail")
        basic = _membership_type(db, "basic-avail")
        space_id, _slot_id = _make_space_and_slot(
            client, admin, allowed=[premium.id]
        )
        blocked, _ = _member_user(
            db, "blocked@examplee6e3b1.com", membership_type=basic
        )
        untyped, _ = _member_user(db, "untyped@examplee6e3b1.com")
        allowed_user, _ = _member_user(
            db, "allowed@examplee6e3b1.com", membership_type=premium
        )
        week = (_future(3) - timedelta(days=_future(3).weekday())).isoformat()
        url = f"/api/v1/spaces/{space_id}/availability?week_start={week}"

        body = client.get(url, cookies=_auth(blocked)).json()
        assert body["eligible"] is False
        assert body["ineligible_reason"] == "membership_type_not_allowed"
        # The week still comes back, so the member sees what they are missing.
        assert body["cells"]

        body = client.get(url, cookies=_auth(untyped)).json()
        assert body["ineligible_reason"] == "no_membership_type"

        body = client.get(url, cookies=_auth(allowed_user)).json()
        assert body["eligible"] is True
        assert body["ineligible_reason"] is None

    def test_unrestricted_space_stays_open(self, client, db):
        _org(db)
        admin = _user(db, "admin")
        space_id, slot_id = _make_space_and_slot(client, admin)
        user, _ = _member_user(db, "open@examplee6e3b1.com")
        week = (_future(3) - timedelta(days=_future(3).weekday())).isoformat()

        body = client.get(
            f"/api/v1/spaces/{space_id}/availability?week_start={week}",
            cookies=_auth(user),
        ).json()
        assert body["eligible"] is True

        r = client.post(
            "/api/v1/bookings",
            json={"space_slot_id": slot_id},
            cookies=_auth(user),
        )
        assert r.status_code == 201
