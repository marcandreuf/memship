"""Integration tests for discount code endpoints."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.activities.models import Activity, ActivityPrice, DiscountCode, Registration
from app.domains.auth.models import User
from app.domains.members.models import Member, MembershipType
from app.domains.persons.models import Person


def _create_user(db, role="admin", suffix=""):
    person = Person(first_name="Disc", last_name="User", email=f"disc-{role}{suffix}@test.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=f"disc-{role}{suffix}@test.com",
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _create_member_with_user(db, suffix=""):
    person = Person(
        first_name="Member", last_name=f"Disc{suffix}",
        email=f"member-disc{suffix}@test.com",
    )
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=f"member-disc{suffix}@test.com",
        password_hash=hash_password("password123"),
        role="member",
        is_active=True,
    )
    db.add(user)
    db.flush()
    existing = db.query(MembershipType).filter(MembershipType.slug == f"gen-disc{suffix}").first()
    if not existing:
        existing = MembershipType(name=f"GenDisc{suffix}", slug=f"gen-disc{suffix}", is_active=True)
        db.add(existing)
        db.flush()
    member = Member(
        person_id=person.id,
        user_id=user.id,
        membership_type_id=existing.id,
        member_number=f"MD{suffix}-{user.id}",
        status="active",
    )
    db.add(member)
    db.flush()
    return user, member


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id, user.role)}


def _create_published_activity(db, admin_id=None, **overrides):
    now = datetime.now(timezone.utc)
    defaults = {
        "name": "Discount Test Activity",
        "slug": f"disc-test-{id(overrides)}",
        "starts_at": now + timedelta(days=10),
        "ends_at": now + timedelta(days=11),
        "registration_starts_at": now - timedelta(days=1),
        "registration_ends_at": now + timedelta(days=9),
        "max_participants": 50,
        "status": "published",
        "is_active": True,
        "features": {},
    }
    defaults.update(overrides)
    if admin_id:
        defaults["created_by"] = admin_id
    activity = Activity(**defaults)
    db.add(activity)
    db.flush()
    price = ActivityPrice(
        activity_id=activity.id, name="Standard", amount=100.00,
        is_default=True, is_active=True,
    )
    db.add(price)
    db.flush()
    return activity, price


class TestDiscountCodeCRUD:
    def test_create_discount_code(self, client, db):
        admin = _create_user(db, "admin", suffix="-dc1")
        activity, _ = _create_published_activity(db, admin.id)
        client.cookies.update(_auth_cookie(admin))

        response = client.post(
            f"/api/v1/activities/{activity.id}/discount-codes/",
            json={
                "code": "SUMMER20",
                "discount_type": "percentage",
                "discount_value": 20,
                "description": "Summer discount",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "SUMMER20"
        assert data["discount_type"] == "percentage"
        assert data["discount_value"] == 20
        assert data["current_uses"] == 0

    def test_create_fixed_discount_code(self, client, db):
        admin = _create_user(db, "admin", suffix="-dc2")
        activity, _ = _create_published_activity(db, admin.id)
        client.cookies.update(_auth_cookie(admin))

        response = client.post(
            f"/api/v1/activities/{activity.id}/discount-codes/",
            json={
                "code": "WELCOME10",
                "discount_type": "fixed",
                "discount_value": 10,
            },
        )
        assert response.status_code == 201
        assert response.json()["discount_type"] == "fixed"
        assert response.json()["discount_value"] == 10

    def test_duplicate_code_fails(self, client, db):
        admin = _create_user(db, "admin", suffix="-dc3")
        activity, _ = _create_published_activity(db, admin.id)
        client.cookies.update(_auth_cookie(admin))

        client.post(
            f"/api/v1/activities/{activity.id}/discount-codes/",
            json={"code": "DUP", "discount_type": "percentage", "discount_value": 10},
        )
        r2 = client.post(
            f"/api/v1/activities/{activity.id}/discount-codes/",
            json={"code": "DUP", "discount_type": "fixed", "discount_value": 5},
        )
        assert r2.status_code == 400
        assert "already exists" in r2.json()["detail"]

    def test_list_discount_codes(self, client, db):
        admin = _create_user(db, "admin", suffix="-dc4")
        activity, _ = _create_published_activity(db, admin.id)
        dc = DiscountCode(
            activity_id=activity.id, code="LIST1",
            discount_type="percentage", discount_value=15, is_active=True,
        )
        db.add(dc)
        db.flush()

        client.cookies.update(_auth_cookie(admin))
        response = client.get(f"/api/v1/activities/{activity.id}/discount-codes/")
        assert response.status_code == 200
        assert len(response.json()) >= 1
        assert any(d["code"] == "LIST1" for d in response.json())

    def test_update_discount_code(self, client, db):
        admin = _create_user(db, "admin", suffix="-dc5")
        activity, _ = _create_published_activity(db, admin.id)
        dc = DiscountCode(
            activity_id=activity.id, code="UPD1",
            discount_type="percentage", discount_value=10, is_active=True,
        )
        db.add(dc)
        db.flush()

        client.cookies.update(_auth_cookie(admin))
        response = client.put(
            f"/api/v1/activities/{activity.id}/discount-codes/{dc.id}",
            json={"discount_value": 25, "description": "Updated"},
        )
        assert response.status_code == 200
        assert response.json()["discount_value"] == 25
        assert response.json()["description"] == "Updated"

    def test_delete_discount_code(self, client, db):
        admin = _create_user(db, "admin", suffix="-dc6")
        activity, _ = _create_published_activity(db, admin.id)
        dc = DiscountCode(
            activity_id=activity.id, code="DEL1",
            discount_type="fixed", discount_value=5, is_active=True,
        )
        db.add(dc)
        db.flush()

        client.cookies.update(_auth_cookie(admin))
        response = client.delete(
            f"/api/v1/activities/{activity.id}/discount-codes/{dc.id}"
        )
        assert response.status_code == 204

    def test_member_cannot_list_codes(self, client, db):
        admin = _create_user(db, "admin", suffix="-dc7")
        user, _ = _create_member_with_user(db, suffix="-dc7")
        activity, _ = _create_published_activity(db, admin.id)

        client.cookies.update(_auth_cookie(user))
        response = client.get(f"/api/v1/activities/{activity.id}/discount-codes/")
        assert response.status_code == 403


class TestValidateDiscount:
    def test_validate_valid_code(self, client, db):
        admin = _create_user(db, "admin", suffix="-val1")
        user, _ = _create_member_with_user(db, suffix="-val1")
        activity, price = _create_published_activity(db, admin.id)
        dc = DiscountCode(
            activity_id=activity.id, code="VALID20",
            discount_type="percentage", discount_value=20, is_active=True,
        )
        db.add(dc)
        db.flush()

        client.cookies.update(_auth_cookie(user))
        response = client.post(
            f"/api/v1/activities/{activity.id}/validate-discount?price_id={price.id}",
            json={"code": "VALID20"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["discount_type"] == "percentage"
        assert data["discount_value"] == 20
        assert data["original_amount"] == 100.0
        assert data["discounted_amount"] == 80.0

    def test_validate_expired_code(self, client, db):
        admin = _create_user(db, "admin", suffix="-val2")
        user, _ = _create_member_with_user(db, suffix="-val2")
        activity, _ = _create_published_activity(db, admin.id)
        now = datetime.now(timezone.utc)
        dc = DiscountCode(
            activity_id=activity.id, code="EXPIRED",
            discount_type="percentage", discount_value=10, is_active=True,
            valid_until=now - timedelta(days=1),
        )
        db.add(dc)
        db.flush()

        client.cookies.update(_auth_cookie(user))
        response = client.post(
            f"/api/v1/activities/{activity.id}/validate-discount",
            json={"code": "EXPIRED"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "expired" in data["error"].lower()

    def test_validate_not_yet_active_code(self, client, db):
        admin = _create_user(db, "admin", suffix="-val3")
        user, _ = _create_member_with_user(db, suffix="-val3")
        activity, _ = _create_published_activity(db, admin.id)
        now = datetime.now(timezone.utc)
        dc = DiscountCode(
            activity_id=activity.id, code="FUTURE",
            discount_type="percentage", discount_value=10, is_active=True,
            valid_from=now + timedelta(days=5),
        )
        db.add(dc)
        db.flush()

        client.cookies.update(_auth_cookie(user))
        response = client.post(
            f"/api/v1/activities/{activity.id}/validate-discount",
            json={"code": "FUTURE"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "not yet active" in data["error"].lower()

    def test_validate_max_uses_reached(self, client, db):
        admin = _create_user(db, "admin", suffix="-val4")
        user, _ = _create_member_with_user(db, suffix="-val4")
        activity, _ = _create_published_activity(db, admin.id)
        dc = DiscountCode(
            activity_id=activity.id, code="MAXED",
            discount_type="percentage", discount_value=10, is_active=True,
            max_uses=1, current_uses=1,
        )
        db.add(dc)
        db.flush()

        client.cookies.update(_auth_cookie(user))
        response = client.post(
            f"/api/v1/activities/{activity.id}/validate-discount",
            json={"code": "MAXED"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "maximum uses" in data["error"].lower()

    def test_validate_not_found(self, client, db):
        admin = _create_user(db, "admin", suffix="-val5")
        user, _ = _create_member_with_user(db, suffix="-val5")
        activity, _ = _create_published_activity(db, admin.id)

        client.cookies.update(_auth_cookie(user))
        response = client.post(
            f"/api/v1/activities/{activity.id}/validate-discount",
            json={"code": "NONEXISTENT"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "not found" in data["error"].lower()


class TestRegisterWithDiscount:
    def test_register_with_percentage_discount(self, client, db):
        admin = _create_user(db, "admin", suffix="-regd1")
        user, member = _create_member_with_user(db, suffix="-regd1")
        activity, price = _create_published_activity(db, admin.id)
        dc = DiscountCode(
            activity_id=activity.id, code="REG20",
            discount_type="percentage", discount_value=20, is_active=True,
        )
        db.add(dc)
        db.flush()

        client.cookies.update(_auth_cookie(user))
        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id, "discount_code": "REG20"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["discount_code_id"] == dc.id
        assert data["original_amount"] == 100.0
        assert data["discounted_amount"] == 80.0

        # Verify usage incremented
        db.refresh(dc)
        assert dc.current_uses == 1

    def test_register_with_fixed_discount(self, client, db):
        admin = _create_user(db, "admin", suffix="-regd2")
        user, member = _create_member_with_user(db, suffix="-regd2")
        activity, price = _create_published_activity(db, admin.id)
        dc = DiscountCode(
            activity_id=activity.id, code="FIX25",
            discount_type="fixed", discount_value=25, is_active=True,
        )
        db.add(dc)
        db.flush()

        client.cookies.update(_auth_cookie(user))
        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id, "discount_code": "FIX25"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["original_amount"] == 100.0
        assert data["discounted_amount"] == 75.0

    def test_register_with_invalid_discount_fails(self, client, db):
        admin = _create_user(db, "admin", suffix="-regd3")
        user, member = _create_member_with_user(db, suffix="-regd3")
        activity, price = _create_published_activity(db, admin.id)

        client.cookies.update(_auth_cookie(user))
        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id, "discount_code": "INVALID"},
        )
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()

    def test_register_with_expired_discount_fails(self, client, db):
        admin = _create_user(db, "admin", suffix="-regd4")
        user, member = _create_member_with_user(db, suffix="-regd4")
        activity, price = _create_published_activity(db, admin.id)
        now = datetime.now(timezone.utc)
        dc = DiscountCode(
            activity_id=activity.id, code="OLDCODE",
            discount_type="percentage", discount_value=10, is_active=True,
            valid_until=now - timedelta(days=1),
        )
        db.add(dc)
        db.flush()

        client.cookies.update(_auth_cookie(user))
        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id, "discount_code": "OLDCODE"},
        )
        assert response.status_code == 400
        assert "expired" in response.json()["detail"].lower()

    def test_discount_usage_incremented(self, client, db):
        admin = _create_user(db, "admin", suffix="-regd5")
        user, member = _create_member_with_user(db, suffix="-regd5")
        activity, price = _create_published_activity(db, admin.id)
        dc = DiscountCode(
            activity_id=activity.id, code="TRACK",
            discount_type="percentage", discount_value=5, is_active=True,
            max_uses=10,
        )
        db.add(dc)
        db.flush()
        assert dc.current_uses == 0

        client.cookies.update(_auth_cookie(user))
        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id, "discount_code": "TRACK"},
        )
        assert response.status_code == 201

        db.refresh(dc)
        assert dc.current_uses == 1

    def test_register_without_discount_stores_amounts(self, client, db):
        """Registration without discount still stores original/discounted amounts (equal)."""
        admin = _create_user(db, "admin", suffix="-regd6")
        user, member = _create_member_with_user(db, suffix="-regd6")
        activity, price = _create_published_activity(db, admin.id)

        client.cookies.update(_auth_cookie(user))
        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["original_amount"] == 100.0
        assert data["discounted_amount"] == 100.0
        assert data["discount_code_id"] is None

    def test_fixed_discount_cannot_go_below_zero(self, client, db):
        """Fixed discount larger than price results in 0, not negative."""
        admin = _create_user(db, "admin", suffix="-regd7")
        user, member = _create_member_with_user(db, suffix="-regd7")
        activity, price = _create_published_activity(db, admin.id)
        dc = DiscountCode(
            activity_id=activity.id, code="BIGFIX",
            discount_type="fixed", discount_value=200, is_active=True,
        )
        db.add(dc)
        db.flush()

        client.cookies.update(_auth_cookie(user))
        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id, "discount_code": "BIGFIX"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["discounted_amount"] == 0.0
