"""Integration tests for Simple Bookings — spaces, dated slots, book/waitlist/cancel."""

from datetime import date, timedelta

import pytest

from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.members.models import Member
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
    email = email or f"{role}-bk@test.com"
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


def _member_user(db, email):
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
        person_id=person.id, user_id=user.id, status="active", is_active=True
    )
    db.add(member)
    db.flush()
    return user, member


def _future(days=3):
    return date.today() + timedelta(days=days)


def _make_space(client, admin, *, open_="08:00:00", close="22:00:00"):
    sp = client.post(
        "/api/v1/spaces",
        json={"name": "Court 1", "open_time": open_, "close_time": close},
        cookies=_auth(admin),
    )
    assert sp.status_code == 201, sp.text
    return sp.json()["id"]


def _make_space_and_slot(client, admin, *, capacity=1, on=None):
    on = on or _future(3)
    space_id = _make_space(client, admin)
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
        user, _ = _member_user(db, "m404@test.com")
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
        user, _ = _member_user(db, "m-nope@test.com")
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
        u1, _ = _member_user(db, "d1@test.com")
        u2, _ = _member_user(db, "d2@test.com")
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
        u1, _ = _member_user(db, "d3@test.com")
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


class TestBooking:
    def test_member_books_a_free_slot(self, client, db):
        _org(db)
        admin = _user(db, "admin")
        _space_id, slot_id = _make_space_and_slot(client, admin)
        user, _ = _member_user(db, "booker@test.com")

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
        u1, _ = _member_user(db, "b1@test.com")
        u2, _ = _member_user(db, "b2@test.com")

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
        u1, _ = _member_user(db, "f1@test.com")
        u2, _ = _member_user(db, "f2@test.com")

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
        u1, _ = _member_user(db, "c1@test.com")
        u2, m2 = _member_user(db, "c2@test.com")

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
        u1, _ = _member_user(db, "occ1@test.com")
        u2, _ = _member_user(db, "occ2@test.com")
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
        u1, _ = _member_user(db, "own1@test.com")
        u2, _ = _member_user(db, "own2@test.com")

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
        u1, _ = _member_user(db, "a1@test.com")
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
