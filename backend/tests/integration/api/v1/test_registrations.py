"""Integration tests for registration endpoints."""

from datetime import datetime, timedelta, timezone

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.activities.models import Activity, ActivityModality, ActivityPrice, Registration
from app.domains.auth.models import User
from app.domains.members.models import Member, MembershipType
from app.domains.persons.models import Person


def _create_user(db, role="admin", suffix=""):
    person = Person(first_name="Reg", last_name="User", email=f"reg-{role}{suffix}@test.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=f"reg-{role}{suffix}@test.com",
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _create_member_with_user(db, suffix="", status="active", membership_type_id=None, date_of_birth=None):
    person = Person(
        first_name="Member", last_name=f"Test{suffix}",
        email=f"member-reg{suffix}@test.com",
        date_of_birth=date_of_birth,
    )
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=f"member-reg{suffix}@test.com",
        password_hash=hash_password("password123"),
        role="member",
        is_active=True,
    )
    db.add(user)
    db.flush()
    mt = membership_type_id
    if not mt:
        existing = db.query(MembershipType).filter(MembershipType.slug == f"gen-reg{suffix}").first()
        if not existing:
            existing = MembershipType(name=f"General{suffix}", slug=f"gen-reg{suffix}", is_active=True)
            db.add(existing)
            db.flush()
        mt = existing.id
    member = Member(
        person_id=person.id,
        user_id=user.id,
        membership_type_id=mt,
        member_number=f"MR{suffix}-{user.id}",
        status=status,
    )
    db.add(member)
    db.flush()
    return user, member


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id, user.role)}


def _create_published_activity(db, admin_id=None, max_participants=50, features=None, **overrides):
    now = datetime.now(timezone.utc)
    defaults = {
        "name": "Reg Test Activity",
        "slug": f"reg-test-{id(overrides)}",
        "starts_at": now + timedelta(days=10),
        "ends_at": now + timedelta(days=11),
        "registration_starts_at": now - timedelta(days=1),
        "registration_ends_at": now + timedelta(days=9),
        "max_participants": max_participants,
        "status": "published",
        "is_active": True,
        "features": features or {},
    }
    defaults.update(overrides)
    if admin_id:
        defaults["created_by"] = admin_id
    activity = Activity(**defaults)
    db.add(activity)
    db.flush()

    # Add a default price
    price = ActivityPrice(
        activity_id=activity.id, name="Standard", amount=50.00,
        is_default=True, is_active=True,
    )
    db.add(price)
    db.flush()
    return activity, price


class TestRegistration:
    def test_register_for_activity(self, client, db):
        admin = _create_user(db, "admin", suffix="-reg1")
        user, member = _create_member_with_user(db, suffix="-reg1")
        activity, price = _create_published_activity(db, admin.id)
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["activity_id"] == activity.id
        assert data["member_id"] == member.id
        assert data["status"] == "confirmed"
        assert data["price_id"] == price.id

    def test_register_with_modality(self, client, db):
        admin = _create_user(db, "admin", suffix="-regmod")
        user, member = _create_member_with_user(db, suffix="-regmod")
        activity, price = _create_published_activity(db, admin.id)
        modality = ActivityModality(
            activity_id=activity.id, name="Morning", max_participants=20, is_active=True,
        )
        db.add(modality)
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id, "modality_id": modality.id},
        )
        assert response.status_code == 201
        assert response.json()["modality_id"] == modality.id

    def test_register_duplicate_fails(self, client, db):
        admin = _create_user(db, "admin", suffix="-regdup")
        user, member = _create_member_with_user(db, suffix="-regdup")
        activity, price = _create_published_activity(db, admin.id)
        client.cookies.update(_auth_cookie(user))

        # First registration
        r1 = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert r1.status_code == 201

        # Duplicate
        r2 = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert r2.status_code == 400
        assert "Already registered" in r2.json()["detail"]

    def test_register_inactive_member_fails(self, client, db):
        admin = _create_user(db, "admin", suffix="-reginact")
        user, member = _create_member_with_user(db, suffix="-reginact", status="suspended")
        activity, price = _create_published_activity(db, admin.id)
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert response.status_code == 400
        assert "not active" in response.json()["detail"]

    def test_register_outside_window_fails(self, client, db):
        admin = _create_user(db, "admin", suffix="-regwin")
        user, member = _create_member_with_user(db, suffix="-regwin")
        now = datetime.now(timezone.utc)
        # Registration window in the future
        activity, price = _create_published_activity(
            db, admin.id,
            slug="reg-future-window",
            registration_starts_at=now + timedelta(days=5),
            registration_ends_at=now + timedelta(days=9),
        )
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert response.status_code == 400
        assert "not opened" in response.json()["detail"]

    def test_register_wrong_membership_type_fails(self, client, db):
        admin = _create_user(db, "admin", suffix="-regmt")
        user, member = _create_member_with_user(db, suffix="-regmt")
        # Activity restricted to membership type 99999 (doesn't match)
        activity, price = _create_published_activity(
            db, admin.id,
            slug="reg-mt-restrict",
            allowed_membership_types=[99999],
        )
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert response.status_code == 400
        assert "Membership type" in response.json()["detail"]

    def test_register_age_restriction_fails(self, client, db):
        admin = _create_user(db, "admin", suffix="-regage")
        # Create member aged ~10 (born 10 years ago)
        from datetime import date
        dob = date(date.today().year - 10, 1, 1)
        user, member = _create_member_with_user(db, suffix="-regage", date_of_birth=dob)
        # Activity requires min age 18
        activity, price = _create_published_activity(
            db, admin.id, slug="reg-age-restrict", min_age=18,
        )
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert response.status_code == 400
        assert "Minimum age" in response.json()["detail"]

    def test_register_full_no_waitlist(self, client, db):
        admin = _create_user(db, "admin", suffix="-regfull")
        user1, member1 = _create_member_with_user(db, suffix="-regfull1")
        user2, member2 = _create_member_with_user(db, suffix="-regfull2")
        activity, price = _create_published_activity(db, admin.id, max_participants=1)

        # First member registers
        client.cookies.update(_auth_cookie(user1))
        r1 = client.post(f"/api/v1/activities/{activity.id}/register", json={"price_id": price.id})
        assert r1.status_code == 201

        # Second member — full, no waitlist
        client.cookies.update(_auth_cookie(user2))
        r2 = client.post(f"/api/v1/activities/{activity.id}/register", json={"price_id": price.id})
        assert r2.status_code == 400
        assert "full" in r2.json()["detail"].lower()

    def test_register_full_with_waitlist(self, client, db):
        admin = _create_user(db, "admin", suffix="-regwl")
        user1, member1 = _create_member_with_user(db, suffix="-regwl1")
        user2, member2 = _create_member_with_user(db, suffix="-regwl2")
        activity, price = _create_published_activity(
            db, admin.id, max_participants=1,
            features={"waiting_list": True},
        )

        # First member — confirmed
        client.cookies.update(_auth_cookie(user1))
        r1 = client.post(f"/api/v1/activities/{activity.id}/register", json={"price_id": price.id})
        assert r1.status_code == 201
        assert r1.json()["status"] == "confirmed"

        # Second member — waitlisted
        client.cookies.update(_auth_cookie(user2))
        r2 = client.post(f"/api/v1/activities/{activity.id}/register", json={"price_id": price.id})
        assert r2.status_code == 201
        assert r2.json()["status"] == "waitlist"


class TestCancelRegistration:
    def test_cancel_own_registration(self, client, db):
        admin = _create_user(db, "admin", suffix="-cancel1")
        user, member = _create_member_with_user(db, suffix="-cancel1")
        activity, price = _create_published_activity(
            db, admin.id, allow_self_cancellation=True,
        )
        # Register
        reg = Registration(
            activity_id=activity.id, member_id=member.id,
            price_id=price.id, status="confirmed",
        )
        db.add(reg)
        activity.current_participants = 1
        db.flush()

        client.cookies.update(_auth_cookie(user))
        response = client.delete(f"/api/v1/registrations/{reg.id}")
        assert response.status_code == 204

    def test_cancel_promotes_waitlist(self, client, db):
        admin = _create_user(db, "admin", suffix="-promo")
        user1, member1 = _create_member_with_user(db, suffix="-promo1")
        user2, member2 = _create_member_with_user(db, suffix="-promo2")
        activity, price = _create_published_activity(
            db, admin.id, max_participants=1,
            features={"waiting_list": True},
            allow_self_cancellation=True,
        )

        # Member 1 confirmed, member 2 waitlisted
        reg1 = Registration(
            activity_id=activity.id, member_id=member1.id,
            price_id=price.id, status="confirmed",
        )
        reg2 = Registration(
            activity_id=activity.id, member_id=member2.id,
            price_id=price.id, status="waitlist",
        )
        db.add_all([reg1, reg2])
        activity.current_participants = 1
        activity.waitlist_count = 1
        db.flush()

        # Member 1 cancels
        client.cookies.update(_auth_cookie(user1))
        response = client.delete(f"/api/v1/registrations/{reg1.id}")
        assert response.status_code == 204

        # Check member 2 got promoted
        db.refresh(reg2)
        assert reg2.status == "confirmed"

    def test_self_cancellation_disabled(self, client, db):
        admin = _create_user(db, "admin", suffix="-nocancel")
        user, member = _create_member_with_user(db, suffix="-nocancel")
        activity, price = _create_published_activity(
            db, admin.id, allow_self_cancellation=False,
        )
        reg = Registration(
            activity_id=activity.id, member_id=member.id,
            price_id=price.id, status="confirmed",
        )
        db.add(reg)
        db.flush()

        client.cookies.update(_auth_cookie(user))
        response = client.delete(f"/api/v1/registrations/{reg.id}")
        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"].lower()

    def test_self_cancellation_deadline_passed(self, client, db):
        admin = _create_user(db, "admin", suffix="-deadline")
        user, member = _create_member_with_user(db, suffix="-deadline")
        now = datetime.now(timezone.utc)
        # Activity starts in 2 hours, deadline is 24h before start
        activity, price = _create_published_activity(
            db, admin.id,
            slug="deadline-act",
            starts_at=now + timedelta(hours=2),
            ends_at=now + timedelta(hours=5),
            allow_self_cancellation=True,
            self_cancellation_deadline_hours=24,
        )
        reg = Registration(
            activity_id=activity.id, member_id=member.id,
            price_id=price.id, status="confirmed",
        )
        db.add(reg)
        db.flush()

        client.cookies.update(_auth_cookie(user))
        response = client.delete(f"/api/v1/registrations/{reg.id}")
        assert response.status_code == 400
        assert "deadline" in response.json()["detail"].lower()

    def test_admin_can_cancel_any(self, client, db):
        admin = _create_user(db, "admin", suffix="-admcancel")
        _, member = _create_member_with_user(db, suffix="-admcancel")
        activity, price = _create_published_activity(db, admin.id)
        reg = Registration(
            activity_id=activity.id, member_id=member.id,
            price_id=price.id, status="confirmed",
        )
        db.add(reg)
        activity.current_participants = 1
        db.flush()

        client.cookies.update(_auth_cookie(admin))
        response = client.delete(f"/api/v1/registrations/{reg.id}")
        assert response.status_code == 204


class TestRegistrationAdmin:
    def test_list_activity_registrations(self, client, db):
        admin = _create_user(db, "admin", suffix="-listreg")
        _, member = _create_member_with_user(db, suffix="-listreg")
        activity, price = _create_published_activity(db, admin.id)
        reg = Registration(
            activity_id=activity.id, member_id=member.id,
            price_id=price.id, status="confirmed",
        )
        db.add(reg)
        db.flush()

        client.cookies.update(_auth_cookie(admin))
        response = client.get(f"/api/v1/activities/{activity.id}/registrations/")
        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["total"] >= 1
        assert data["items"][0]["member"]["first_name"] == "Member"

    def test_admin_change_status(self, client, db):
        admin = _create_user(db, "admin", suffix="-chgstat")
        _, member = _create_member_with_user(db, suffix="-chgstat")
        activity, price = _create_published_activity(db, admin.id)
        reg = Registration(
            activity_id=activity.id, member_id=member.id,
            price_id=price.id, status="confirmed",
        )
        db.add(reg)
        activity.current_participants = 1
        db.flush()

        client.cookies.update(_auth_cookie(admin))
        response = client.put(
            f"/api/v1/registrations/{reg.id}/status",
            json={"status": "cancelled"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"

    def test_member_cannot_list_registrations(self, client, db):
        admin = _create_user(db, "admin", suffix="-memlist")
        user, _ = _create_member_with_user(db, suffix="-memlist")
        activity, _ = _create_published_activity(db, admin.id)

        client.cookies.update(_auth_cookie(user))
        response = client.get(f"/api/v1/activities/{activity.id}/registrations/")
        assert response.status_code == 403


class TestMyRegistrations:
    def test_list_my_registrations(self, client, db):
        admin = _create_user(db, "admin", suffix="-myreg")
        user, member = _create_member_with_user(db, suffix="-myreg")
        activity, price = _create_published_activity(db, admin.id)
        reg = Registration(
            activity_id=activity.id, member_id=member.id,
            price_id=price.id, status="confirmed",
        )
        db.add(reg)
        db.flush()

        client.cookies.update(_auth_cookie(user))
        response = client.get("/api/v1/members/me/registrations")
        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["total"] >= 1
        assert data["items"][0]["activity_id"] == activity.id


class TestEligibility:
    def test_check_eligibility_eligible(self, client, db):
        admin = _create_user(db, "admin", suffix="-elig1")
        user, member = _create_member_with_user(db, suffix="-elig1")
        activity, _ = _create_published_activity(db, admin.id)

        client.cookies.update(_auth_cookie(user))
        response = client.get(f"/api/v1/activities/{activity.id}/eligibility")
        assert response.status_code == 200
        data = response.json()
        assert data["eligible"] is True
        assert data["reasons"] == []

    def test_check_eligibility_inactive_member(self, client, db):
        admin = _create_user(db, "admin", suffix="-eliginact")
        user, member = _create_member_with_user(db, suffix="-eliginact", status="suspended")
        activity, _ = _create_published_activity(db, admin.id)

        client.cookies.update(_auth_cookie(user))
        response = client.get(f"/api/v1/activities/{activity.id}/eligibility")
        assert response.status_code == 200
        data = response.json()
        assert data["eligible"] is False
        assert any("not active" in r for r in data["reasons"])

    def test_capacity_counter_updates(self, client, db):
        admin = _create_user(db, "admin", suffix="-counter")
        user, member = _create_member_with_user(db, suffix="-counter")
        activity, price = _create_published_activity(db, admin.id)

        client.cookies.update(_auth_cookie(user))
        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert response.status_code == 201

        # Check counters updated
        db.refresh(activity)
        assert activity.current_participants == 1

        db.refresh(price)
        assert price.current_registrations == 1
