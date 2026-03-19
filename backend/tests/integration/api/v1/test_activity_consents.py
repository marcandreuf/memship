"""Integration tests for activity consent endpoints and registration consent flow."""

from datetime import datetime, timedelta, timezone

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.activities.models import Activity, ActivityConsent, ActivityPrice, Registration
from app.domains.auth.models import User
from app.domains.members.models import Member, MembershipType
from app.domains.persons.models import Person


def _create_user(db, role="admin", suffix=""):
    person = Person(first_name="Cons", last_name="User", email=f"cons-{role}{suffix}@test.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id, email=f"cons-{role}{suffix}@test.com",
        password_hash=hash_password("password123"), role=role, is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _create_member_with_user(db, suffix=""):
    person = Person(
        first_name="Member", last_name=f"Cons{suffix}",
        email=f"member-cons{suffix}@test.com",
    )
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id, email=f"member-cons{suffix}@test.com",
        password_hash=hash_password("password123"), role="member", is_active=True,
    )
    db.add(user)
    db.flush()
    existing = db.query(MembershipType).filter(MembershipType.slug == f"gen-cons{suffix}").first()
    if not existing:
        existing = MembershipType(name=f"GenCons{suffix}", slug=f"gen-cons{suffix}", is_active=True)
        db.add(existing)
        db.flush()
    member = Member(
        person_id=person.id, user_id=user.id, membership_type_id=existing.id,
        member_number=f"MC{suffix}-{user.id}", status="active",
    )
    db.add(member)
    db.flush()
    return user, member


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id, user.role)}


def _create_published_activity(db, admin_id=None, **overrides):
    now = datetime.now(timezone.utc)
    defaults = {
        "name": "Consent Test Activity",
        "slug": f"cons-test-{id(overrides)}",
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
        activity_id=activity.id, name="Standard", amount=50.00,
        is_default=True, is_active=True,
    )
    db.add(price)
    db.flush()
    return activity, price


class TestActivityConsentCRUD:
    def test_create_consent(self, client, db):
        admin = _create_user(db, "admin", suffix="-cc1")
        activity, _ = _create_published_activity(db, admin.id)
        client.cookies.update(_auth_cookie(admin))

        response = client.post(
            f"/api/v1/activities/{activity.id}/consents/",
            json={
                "title": "Liability Waiver",
                "content": "I accept all risks associated with this activity.",
                "is_mandatory": True,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Liability Waiver"
        assert data["is_mandatory"] is True

    def test_list_consents(self, client, db):
        admin = _create_user(db, "admin", suffix="-cc2")
        user, _ = _create_member_with_user(db, suffix="-cc2")
        activity, _ = _create_published_activity(db, admin.id)
        consent = ActivityConsent(
            activity_id=activity.id, title="Waiver", content="Accept risks.",
            is_mandatory=True, is_active=True,
        )
        db.add(consent)
        db.flush()

        # Members can list consents too
        client.cookies.update(_auth_cookie(user))
        response = client.get(f"/api/v1/activities/{activity.id}/consents/")
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_update_consent(self, client, db):
        admin = _create_user(db, "admin", suffix="-cc3")
        activity, _ = _create_published_activity(db, admin.id)
        consent = ActivityConsent(
            activity_id=activity.id, title="Old Title", content="Old content.",
            is_mandatory=True, is_active=True,
        )
        db.add(consent)
        db.flush()

        client.cookies.update(_auth_cookie(admin))
        response = client.put(
            f"/api/v1/activities/{activity.id}/consents/{consent.id}",
            json={"title": "New Title", "content": "Updated content."},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "New Title"

    def test_delete_consent(self, client, db):
        admin = _create_user(db, "admin", suffix="-cc4")
        activity, _ = _create_published_activity(db, admin.id)
        consent = ActivityConsent(
            activity_id=activity.id, title="Delete Me", content="...",
            is_mandatory=False, is_active=True,
        )
        db.add(consent)
        db.flush()

        client.cookies.update(_auth_cookie(admin))
        response = client.delete(
            f"/api/v1/activities/{activity.id}/consents/{consent.id}"
        )
        assert response.status_code == 204

    def test_member_cannot_create_consent(self, client, db):
        admin = _create_user(db, "admin", suffix="-cc5")
        user, _ = _create_member_with_user(db, suffix="-cc5")
        activity, _ = _create_published_activity(db, admin.id)

        client.cookies.update(_auth_cookie(user))
        response = client.post(
            f"/api/v1/activities/{activity.id}/consents/",
            json={"title": "Sneaky", "content": "Should not work."},
        )
        assert response.status_code == 403


class TestRegistrationWithConsents:
    def test_register_with_mandatory_consent(self, client, db):
        admin = _create_user(db, "admin", suffix="-rc1")
        user, member = _create_member_with_user(db, suffix="-rc1")
        activity, price = _create_published_activity(db, admin.id)
        consent = ActivityConsent(
            activity_id=activity.id, title="Liability Waiver",
            content="I accept all risks.", is_mandatory=True, is_active=True,
        )
        db.add(consent)
        db.flush()

        client.cookies.update(_auth_cookie(user))
        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={
                "price_id": price.id,
                "consents": [{"activity_consent_id": consent.id, "accepted": True}],
            },
        )
        assert response.status_code == 201

    def test_register_without_mandatory_consent_fails(self, client, db):
        admin = _create_user(db, "admin", suffix="-rc2")
        user, member = _create_member_with_user(db, suffix="-rc2")
        activity, price = _create_published_activity(db, admin.id)
        consent = ActivityConsent(
            activity_id=activity.id, title="Required Waiver",
            content="Must accept.", is_mandatory=True, is_active=True,
        )
        db.add(consent)
        db.flush()

        client.cookies.update(_auth_cookie(user))
        # Register without accepting consents
        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert response.status_code == 400
        assert "Mandatory consents not accepted" in response.json()["detail"]

    def test_register_with_declined_mandatory_consent_fails(self, client, db):
        admin = _create_user(db, "admin", suffix="-rc3")
        user, member = _create_member_with_user(db, suffix="-rc3")
        activity, price = _create_published_activity(db, admin.id)
        consent = ActivityConsent(
            activity_id=activity.id, title="Must Accept",
            content="Required.", is_mandatory=True, is_active=True,
        )
        db.add(consent)
        db.flush()

        client.cookies.update(_auth_cookie(user))
        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={
                "price_id": price.id,
                "consents": [{"activity_consent_id": consent.id, "accepted": False}],
            },
        )
        assert response.status_code == 400
        assert "Mandatory consents not accepted" in response.json()["detail"]

    def test_register_without_optional_consent_succeeds(self, client, db):
        admin = _create_user(db, "admin", suffix="-rc4")
        user, member = _create_member_with_user(db, suffix="-rc4")
        activity, price = _create_published_activity(db, admin.id)
        consent = ActivityConsent(
            activity_id=activity.id, title="Image Rights",
            content="Optional image usage.", is_mandatory=False, is_active=True,
        )
        db.add(consent)
        db.flush()

        client.cookies.update(_auth_cookie(user))
        # Register without accepting optional consent — should work
        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )
        assert response.status_code == 201

    def test_register_with_mixed_consents(self, client, db):
        """Mandatory accepted + optional skipped = success."""
        admin = _create_user(db, "admin", suffix="-rc5")
        user, member = _create_member_with_user(db, suffix="-rc5")
        activity, price = _create_published_activity(db, admin.id)
        mandatory = ActivityConsent(
            activity_id=activity.id, title="Liability",
            content="Required.", is_mandatory=True, is_active=True,
        )
        optional = ActivityConsent(
            activity_id=activity.id, title="Photos",
            content="Optional.", is_mandatory=False, is_active=True,
        )
        db.add_all([mandatory, optional])
        db.flush()

        client.cookies.update(_auth_cookie(user))
        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={
                "price_id": price.id,
                "consents": [{"activity_consent_id": mandatory.id, "accepted": True}],
            },
        )
        assert response.status_code == 201
