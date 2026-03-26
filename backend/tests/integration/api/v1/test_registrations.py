"""Integration tests for registration endpoints."""

import time
from datetime import date, datetime, timedelta, timezone

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


class TestRegistrationStats:
    def test_stats_returns_counts(self, client, db):
        admin = _create_user(db, "admin", suffix="-stats")
        user, member = _create_member_with_user(db, suffix="-stats")
        activity, price = _create_published_activity(db, admin.id)
        db.add(Registration(
            activity_id=activity.id, member_id=member.id,
            price_id=price.id, status="confirmed",
        ))
        db.flush()

        client.cookies.update(_auth_cookie(admin))
        response = client.get("/api/v1/registrations/stats")
        assert response.status_code == 200
        data = response.json()
        assert "confirmed" in data
        assert "waitlist" in data
        assert "cancelled" in data
        assert "pending" in data
        assert "total" in data
        assert data["confirmed"] >= 1
        assert data["total"] >= 1

    def test_stats_requires_admin(self, client, db):
        user, _ = _create_member_with_user(db, suffix="-stats-member")
        client.cookies.update(_auth_cookie(user))
        response = client.get("/api/v1/registrations/stats")
        assert response.status_code == 403


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


class TestAutoReceipt:
    """Test that confirmed registrations auto-generate a receipt."""

    def test_registration_creates_receipt(self, client, db):
        """Confirmed registration with amount > 0 creates a pending receipt."""
        from app.domains.billing.models import Receipt
        from app.domains.organizations.models import OrganizationSettings

        # Ensure org settings exist for receipt number generation
        org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
        if not org:
            db.add(OrganizationSettings(
                id=1, name="Test Org", locale="es", timezone="Europe/Madrid",
                currency="EUR", date_format="DD/MM/YYYY",
                invoice_prefix="FAC", invoice_next_number=1,
                invoice_annual_reset=True, default_vat_rate=21,
            ))
            db.flush()

        admin = _create_user(db, "admin", suffix="-autorec")
        user, member = _create_member_with_user(db, suffix="-autorec")
        activity, price = _create_published_activity(db, admin.id)
        # price.amount = 50.00 from _create_published_activity

        client.cookies.update(_auth_cookie(user))
        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert response.status_code == 201
        assert response.json()["status"] == "confirmed"

        # Check receipt was created
        receipt = db.query(Receipt).filter(
            Receipt.member_id == member.id,
            Receipt.registration_id == response.json()["id"],
        ).first()
        assert receipt is not None
        assert receipt.origin == "activity"
        assert receipt.status == "emitted"
        assert float(receipt.base_amount) == 50.00
        assert receipt.receipt_number.startswith("FAC-")

    def test_waitlisted_registration_no_receipt(self, client, db):
        """Waitlisted registration should NOT create a receipt."""
        from app.domains.billing.models import Receipt
        from app.domains.organizations.models import OrganizationSettings

        org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
        if not org:
            db.add(OrganizationSettings(
                id=1, name="Test Org", locale="es", timezone="Europe/Madrid",
                currency="EUR", date_format="DD/MM/YYYY",
                invoice_prefix="FAC", invoice_next_number=1,
            ))
            db.flush()

        admin = _create_user(db, "admin", suffix="-nowlrec")
        user1, member1 = _create_member_with_user(db, suffix="-nowlrec1")
        user2, member2 = _create_member_with_user(db, suffix="-nowlrec2")
        activity, price = _create_published_activity(
            db, admin.id, max_participants=1,
            features={"waiting_list": True},
        )

        # First member confirms
        client.cookies.update(_auth_cookie(user1))
        client.post(f"/api/v1/activities/{activity.id}/register", json={"price_id": price.id})

        # Second member waitlisted
        client.cookies.update(_auth_cookie(user2))
        r = client.post(f"/api/v1/activities/{activity.id}/register", json={"price_id": price.id})
        assert r.status_code == 201
        assert r.json()["status"] == "waitlist"

        # No receipt for waitlisted member
        receipt = db.query(Receipt).filter(
            Receipt.member_id == member2.id,
            Receipt.registration_id == r.json()["id"],
        ).first()
        assert receipt is None


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


class TestWaitlistAndCapacity:
    """Section 7: Waiting List & Capacity tests."""

    def test_waitlist_fifo_order_with_multiple_members(self, client, db):
        """7.2 — When a confirmed member cancels, the OLDEST waitlisted member is promoted."""
        admin = _create_user(db, "admin", suffix="-fifo")
        user1, member1 = _create_member_with_user(db, suffix="-fifo1")
        user2, member2 = _create_member_with_user(db, suffix="-fifo2")
        user3, member3 = _create_member_with_user(db, suffix="-fifo3")
        activity, price = _create_published_activity(
            db, admin.id, max_participants=1,
            features={"waiting_list": True},
            allow_self_cancellation=True,
        )

        # Member 1 confirmed
        reg1 = Registration(
            activity_id=activity.id, member_id=member1.id,
            price_id=price.id, status="confirmed",
        )
        db.add(reg1)
        db.flush()

        # Member 2 waitlisted first (older timestamp)
        reg2 = Registration(
            activity_id=activity.id, member_id=member2.id,
            price_id=price.id, status="waitlist",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        db.add(reg2)
        db.flush()

        # Member 3 waitlisted second (newer timestamp)
        reg3 = Registration(
            activity_id=activity.id, member_id=member3.id,
            price_id=price.id, status="waitlist",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        db.add(reg3)
        activity.current_participants = 1
        activity.waitlist_count = 2
        db.flush()

        # Member 1 cancels
        client.cookies.update(_auth_cookie(user1))
        response = client.delete(f"/api/v1/registrations/{reg1.id}")
        assert response.status_code == 204

        # Member 2 (oldest waitlisted) should be promoted, not member 3
        db.refresh(reg2)
        db.refresh(reg3)
        assert reg2.status == "confirmed"
        assert reg3.status == "waitlist"

    def test_waitlist_counter_increments_on_waitlist_registration(self, client, db):
        """Waitlist counter increments when a member gets waitlisted."""
        admin = _create_user(db, "admin", suffix="-wlcnt")
        user1, member1 = _create_member_with_user(db, suffix="-wlcnt1")
        user2, member2 = _create_member_with_user(db, suffix="-wlcnt2")
        activity, price = _create_published_activity(
            db, admin.id, max_participants=1,
            features={"waiting_list": True},
        )

        # First member confirms
        client.cookies.update(_auth_cookie(user1))
        client.post(f"/api/v1/activities/{activity.id}/register", json={"price_id": price.id})

        # Second member gets waitlisted
        client.cookies.update(_auth_cookie(user2))
        r = client.post(f"/api/v1/activities/{activity.id}/register", json={"price_id": price.id})
        assert r.status_code == 201
        assert r.json()["status"] == "waitlist"

        db.refresh(activity)
        assert activity.waitlist_count == 1

    def test_waitlist_counter_decrements_on_promotion(self, client, db):
        """Waitlist counter decrements when a waitlisted member is promoted."""
        admin = _create_user(db, "admin", suffix="-wldec")
        user1, member1 = _create_member_with_user(db, suffix="-wldec1")
        user2, member2 = _create_member_with_user(db, suffix="-wldec2")
        activity, price = _create_published_activity(
            db, admin.id, max_participants=1,
            features={"waiting_list": True},
            allow_self_cancellation=True,
        )

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

        # Cancel confirmed → promotes waitlisted
        client.cookies.update(_auth_cookie(user1))
        client.delete(f"/api/v1/registrations/{reg1.id}")

        db.refresh(activity)
        assert activity.current_participants == 1  # re-incremented by promotion
        assert activity.waitlist_count == 0

    def test_cancel_waitlisted_does_not_decrement_participants(self, client, db):
        """Cancelling a waitlisted registration should not decrement current_participants."""
        admin = _create_user(db, "admin", suffix="-wlcancel")
        user1, member1 = _create_member_with_user(db, suffix="-wlcancel1")
        user2, member2 = _create_member_with_user(db, suffix="-wlcancel2")
        activity, price = _create_published_activity(
            db, admin.id, max_participants=1,
            features={"waiting_list": True},
            allow_self_cancellation=True,
        )

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

        # Cancel the waitlisted member
        client.cookies.update(_auth_cookie(user2))
        response = client.delete(f"/api/v1/registrations/{reg2.id}")
        assert response.status_code == 204

        db.refresh(activity)
        assert activity.current_participants == 1  # unchanged
        assert activity.waitlist_count == 0  # decremented

    def test_modality_capacity_triggers_waitlist(self, client, db):
        """When modality is full but activity has space, member gets waitlisted."""
        admin = _create_user(db, "admin", suffix="-modcap")
        user1, member1 = _create_member_with_user(db, suffix="-modcap1")
        user2, member2 = _create_member_with_user(db, suffix="-modcap2")
        activity, price = _create_published_activity(
            db, admin.id, max_participants=50,
            features={"waiting_list": True},
        )
        modality = ActivityModality(
            activity_id=activity.id, name="Morning", max_participants=1,
            is_active=True, current_participants=0,
        )
        db.add(modality)
        db.flush()

        # First member confirms in modality
        client.cookies.update(_auth_cookie(user1))
        r1 = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id, "modality_id": modality.id},
        )
        assert r1.status_code == 201
        assert r1.json()["status"] == "confirmed"

        # Second member — modality full → waitlisted
        client.cookies.update(_auth_cookie(user2))
        r2 = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id, "modality_id": modality.id},
        )
        assert r2.status_code == 201
        assert r2.json()["status"] == "waitlist"

    def test_modality_full_no_waitlist_rejects(self, client, db):
        """When modality is full and no waitlist, registration is rejected."""
        admin = _create_user(db, "admin", suffix="-modrej")
        user1, member1 = _create_member_with_user(db, suffix="-modrej1")
        user2, member2 = _create_member_with_user(db, suffix="-modrej2")
        activity, price = _create_published_activity(
            db, admin.id, max_participants=50,
            features={},
        )
        modality = ActivityModality(
            activity_id=activity.id, name="Morning", max_participants=1,
            is_active=True, current_participants=0,
        )
        db.add(modality)
        db.flush()

        # First member confirms in modality
        client.cookies.update(_auth_cookie(user1))
        client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id, "modality_id": modality.id},
        )

        # Second member — modality full, no waitlist → rejected
        client.cookies.update(_auth_cookie(user2))
        r2 = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id, "modality_id": modality.id},
        )
        assert r2.status_code == 400
        assert "full" in r2.json()["detail"].lower()

    def test_modality_counter_updates_on_registration(self, client, db):
        """Modality current_participants increments on confirmed registration."""
        admin = _create_user(db, "admin", suffix="-modcnt")
        user, member = _create_member_with_user(db, suffix="-modcnt")
        activity, price = _create_published_activity(db, admin.id)
        modality = ActivityModality(
            activity_id=activity.id, name="Morning", max_participants=20,
            is_active=True, current_participants=0,
        )
        db.add(modality)
        db.flush()

        client.cookies.update(_auth_cookie(user))
        r = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id, "modality_id": modality.id},
        )
        assert r.status_code == 201

        db.refresh(modality)
        assert modality.current_participants == 1


class TestEligibilityRules:
    """Section 8: Eligibility Rules tests."""

    def test_max_age_restriction_fails(self, client, db):
        """8.1 — Adult cannot register for kids-only activity (max_age)."""
        admin = _create_user(db, "admin", suffix="-maxage")
        dob = date(date.today().year - 30, 6, 15)  # 30 years old
        user, member = _create_member_with_user(db, suffix="-maxage", date_of_birth=dob)
        activity, price = _create_published_activity(
            db, admin.id, slug="kids-only", max_age=12,
        )
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert response.status_code == 400
        assert "Maximum age" in response.json()["detail"] or "age" in response.json()["detail"].lower()

    def test_age_within_range_passes(self, client, db):
        """8.3 — Member within age range can register."""
        admin = _create_user(db, "admin", suffix="-ageok")
        dob = date(date.today().year - 25, 6, 15)  # 25 years old
        user, member = _create_member_with_user(db, suffix="-ageok", date_of_birth=dob)
        activity, price = _create_published_activity(
            db, admin.id, slug="age-range-ok", min_age=18, max_age=35,
        )
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert response.status_code == 201
        assert response.json()["status"] == "confirmed"

    def test_age_boundary_exact_min_age_passes(self, client, db):
        """Member exactly at min_age should pass eligibility."""
        admin = _create_user(db, "admin", suffix="-agemin")
        # Born exactly 16 years ago today
        today = date.today()
        dob = date(today.year - 16, today.month, today.day)
        user, member = _create_member_with_user(db, suffix="-agemin", date_of_birth=dob)
        activity, price = _create_published_activity(
            db, admin.id, slug="age-min-boundary", min_age=16,
        )
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert response.status_code == 201

    def test_age_boundary_one_year_below_min_age_fails(self, client, db):
        """Member one year below min_age should fail eligibility."""
        admin = _create_user(db, "admin", suffix="-agemin1d")
        today = date.today()
        # Born 15 years ago → age 15, min_age 16
        dob = date(today.year - 15, today.month, today.day)
        user, member = _create_member_with_user(db, suffix="-agemin1d", date_of_birth=dob)
        activity, price = _create_published_activity(
            db, admin.id, slug="age-min-boundary-fail", min_age=16,
        )
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert response.status_code == 400
        assert "age" in response.json()["detail"].lower()

    def test_reregister_after_cancellation(self, client, db):
        """8.5 — Member can register again after cancelling."""
        admin = _create_user(db, "admin", suffix="-rereg")
        user, member = _create_member_with_user(db, suffix="-rereg")
        activity, price = _create_published_activity(
            db, admin.id, allow_self_cancellation=True,
        )

        client.cookies.update(_auth_cookie(user))

        # Register
        r1 = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert r1.status_code == 201
        reg_id = r1.json()["id"]

        # Cancel
        r2 = client.delete(f"/api/v1/registrations/{reg_id}")
        assert r2.status_code == 204

        # Re-register
        r3 = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert r3.status_code == 201
        assert r3.json()["status"] == "confirmed"

    def test_duplicate_while_waitlisted_fails(self, client, db):
        """8.5 — Cannot register again while already waitlisted."""
        admin = _create_user(db, "admin", suffix="-dupwl")
        user, member = _create_member_with_user(db, suffix="-dupwl")
        activity, price = _create_published_activity(
            db, admin.id, max_participants=0,
            features={"waiting_list": True},
        )

        client.cookies.update(_auth_cookie(user))

        # First registration → waitlisted (0 capacity)
        r1 = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert r1.status_code == 201
        assert r1.json()["status"] == "waitlist"

        # Try again → duplicate
        r2 = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert r2.status_code == 400
        assert "Already registered" in r2.json()["detail"]

    def test_registration_window_closed_fails(self, client, db):
        """8.6 — Cannot register when registration window has closed."""
        admin = _create_user(db, "admin", suffix="-closed")
        user, member = _create_member_with_user(db, suffix="-closed")
        now = datetime.now(timezone.utc)
        activity, price = _create_published_activity(
            db, admin.id, slug="reg-closed",
            registration_starts_at=now - timedelta(days=10),
            registration_ends_at=now - timedelta(days=1),
        )
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert response.status_code == 400
        assert "closed" in response.json()["detail"].lower()

    def test_pending_member_cannot_register(self, client, db):
        """8.7 — Pending member is rejected."""
        admin = _create_user(db, "admin", suffix="-pending")
        user, member = _create_member_with_user(db, suffix="-pending", status="pending")
        activity, price = _create_published_activity(db, admin.id)
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert response.status_code == 400
        assert "not active" in response.json()["detail"]

    def test_cancelled_member_cannot_register(self, client, db):
        """8.7 — Cancelled member is rejected."""
        admin = _create_user(db, "admin", suffix="-cmem")
        user, member = _create_member_with_user(db, suffix="-cmem", status="cancelled")
        activity, price = _create_published_activity(db, admin.id)
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert response.status_code == 400
        assert "not active" in response.json()["detail"]

    def test_expired_member_cannot_register(self, client, db):
        """8.7 — Expired member is rejected."""
        admin = _create_user(db, "admin", suffix="-expm")
        user, member = _create_member_with_user(db, suffix="-expm", status="expired")
        activity, price = _create_published_activity(db, admin.id)
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert response.status_code == 400
        assert "not active" in response.json()["detail"]

    def test_draft_activity_not_eligible(self, client, db):
        """Cannot register for a draft activity."""
        admin = _create_user(db, "admin", suffix="-draft")
        user, member = _create_member_with_user(db, suffix="-draft")
        now = datetime.now(timezone.utc)
        activity, price = _create_published_activity(db, admin.id, slug="draft-act")
        activity.status = "draft"
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert response.status_code == 400
        assert "not open" in response.json()["detail"].lower() or "not published" in response.json()["detail"].lower()

    def test_archived_activity_not_eligible(self, client, db):
        """Cannot register for an archived activity."""
        admin = _create_user(db, "admin", suffix="-arch")
        user, member = _create_member_with_user(db, suffix="-arch")
        activity, price = _create_published_activity(db, admin.id, slug="arch-act")
        activity.status = "archived"
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert response.status_code == 400

    def test_cancelled_activity_not_eligible(self, client, db):
        """Cannot register for a cancelled activity."""
        admin = _create_user(db, "admin", suffix="-cact")
        user, member = _create_member_with_user(db, suffix="-cact")
        activity, price = _create_published_activity(db, admin.id, slug="cancel-act")
        activity.status = "cancelled"
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert response.status_code == 400

    def test_eligibility_accumulates_multiple_reasons(self, client, db):
        """Eligibility check returns all failing reasons, not just the first."""
        admin = _create_user(db, "admin", suffix="-multi")
        dob = date(date.today().year - 10, 1, 1)  # 10 years old
        user, member = _create_member_with_user(
            db, suffix="-multi", status="suspended", date_of_birth=dob,
        )
        now = datetime.now(timezone.utc)
        activity, _ = _create_published_activity(
            db, admin.id, slug="multi-fail",
            min_age=18,
            registration_starts_at=now + timedelta(days=5),
            registration_ends_at=now + timedelta(days=9),
        )
        client.cookies.update(_auth_cookie(user))

        response = client.get(f"/api/v1/activities/{activity.id}/eligibility")
        assert response.status_code == 200
        data = response.json()
        assert data["eligible"] is False
        # Should have at least 3 reasons: not active, too young, window not open
        assert len(data["reasons"]) >= 3
