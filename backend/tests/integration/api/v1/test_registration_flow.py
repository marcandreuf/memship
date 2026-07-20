"""Integration tests for the v1.2.0 registration / approval flow."""

from datetime import datetime, timedelta, timezone

from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person

REGISTER_PAYLOAD = {
    "first_name": "Nova",
    "last_name": "Aplicant",
    "email": "nova@test.com",
    "password": "password123",
}


def _ensure_membership_type(db):
    mt = db.query(MembershipType).first()
    if not mt:
        mt = MembershipType(name="General", slug="general", is_active=True)
        db.add(mt)
        db.flush()
    return mt


def _set_features(db, **flags):
    """Set org feature flags, creating the single-tenant settings row if needed."""
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(id=1, name="Test Club")
        db.add(org)
        db.flush()
    org.features = {**(org.features or {}), **flags}
    db.flush()
    return org


def _create_user(db, email, role="member", status="active", password="password123"):
    person = Person(first_name="Test", last_name="User", email=email)
    db.add(person)
    db.flush()

    user = User(
        person_id=person.id,
        email=email,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
        email_verified=True,
    )
    db.add(user)
    db.flush()

    mt = _ensure_membership_type(db)
    member = Member(
        person_id=person.id,
        user_id=user.id,
        membership_type_id=mt.id,
        member_number=None if status == "pending" else f"M-{user.id:04d}",
        status=status,
    )
    db.add(member)
    db.flush()
    return user, member


def _login(client, email, password="password123"):
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response


def _register(client, db, **overrides):
    _ensure_membership_type(db)
    payload = {**REGISTER_PAYLOAD, **overrides}
    return client.post("/api/v1/auth/register", json=payload)


class TestRegistrationCreatesPendingMember:
    def test_register_lands_in_pending_without_number_or_session(self, client, db):
        response = _register(client, db)

        assert response.status_code == 201
        data = response.json()
        assert data["member_status"] == "pending"
        assert data["requires_approval"] is True
        assert "access_token" not in response.cookies

        member = (
            db.query(Member)
            .join(Person, Member.person_id == Person.id)
            .filter(Person.email == REGISTER_PAYLOAD["email"])
            .first()
        )
        assert member.status == "pending"
        assert member.member_number is None

    def test_register_issues_verification_token_and_leaves_email_unverified(
        self, client, db
    ):
        response = _register(client, db)

        # No email transport in tests, so the token comes back in the body.
        assert response.json()["verification_token"]

        user = db.query(User).filter(User.email == REGISTER_PAYLOAD["email"]).first()
        assert user.email_verified is False
        assert user.verification_token is not None

    def test_register_blocked_when_public_registration_disabled(self, client, db):
        _set_features(db, public_registration=False)

        response = _register(client, db)

        assert response.status_code == 403
        assert "disabled" in response.json()["detail"].lower()

    def test_register_activates_immediately_when_approval_not_required(self, client, db):
        _set_features(db, registration_requires_approval=False)

        response = _register(client, db)

        assert response.status_code == 201
        assert response.json()["member_status"] == "active"
        assert response.json()["requires_approval"] is False

        member = (
            db.query(Member)
            .join(Person, Member.person_id == Person.id)
            .filter(Person.email == REGISTER_PAYLOAD["email"])
            .first()
        )
        assert member.status == "active"
        assert member.member_number is not None


class TestEmailVerification:
    def test_verify_email_with_valid_token(self, client, db):
        token = _register(client, db).json()["verification_token"]

        response = client.post("/api/v1/auth/verify-email", json={"token": token})

        assert response.status_code == 200
        user = db.query(User).filter(User.email == REGISTER_PAYLOAD["email"]).first()
        assert user.email_verified is True
        assert user.email_verified_at is not None
        assert user.verification_token is None

    def test_verify_email_rejects_unknown_token(self, client, db):
        response = client.post("/api/v1/auth/verify-email", json={"token": "nope"})
        assert response.status_code == 400

    def test_verify_email_rejects_expired_token(self, client, db):
        token = _register(client, db).json()["verification_token"]
        user = db.query(User).filter(User.email == REGISTER_PAYLOAD["email"]).first()
        user.verification_token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.flush()

        response = client.post("/api/v1/auth/verify-email", json={"token": token})

        assert response.status_code == 400
        db.refresh(user)
        assert user.email_verified is False

    def test_verify_email_token_is_single_use(self, client, db):
        token = _register(client, db).json()["verification_token"]
        client.post("/api/v1/auth/verify-email", json={"token": token})

        response = client.post("/api/v1/auth/verify-email", json={"token": token})

        assert response.status_code == 400

    def test_resend_verification_issues_a_new_token(self, client, db):
        first_token = _register(client, db).json()["verification_token"]

        response = client.post(
            "/api/v1/auth/resend-verification",
            json={"email": REGISTER_PAYLOAD["email"]},
        )

        assert response.status_code == 200
        new_token = response.json()["verification_token"]
        assert new_token and new_token != first_token

    def test_resend_verification_is_silent_for_unknown_email(self, client, db):
        response = client.post(
            "/api/v1/auth/resend-verification", json={"email": "ghost@test.com"}
        )

        assert response.status_code == 200
        assert response.json()["verification_token"] is None

    def test_resend_verification_is_silent_for_already_verified_user(self, client, db):
        _create_user(db, email="verified@test.com")

        response = client.post(
            "/api/v1/auth/resend-verification", json={"email": "verified@test.com"}
        )

        assert response.status_code == 200
        assert response.json()["verification_token"] is None


class TestAdminApproval:
    def test_approve_allocates_number_and_activates(self, client, db):
        _create_user(db, email="admin@test.com", role="admin")
        _, pending = _create_user(db, email="pending@test.com", status="pending")
        _login(client, "admin@test.com")

        response = client.post(f"/api/v1/members/{pending.id}/approve")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "active"
        assert body["member_number"]

        db.refresh(pending)
        assert pending.status == "active"
        assert pending.member_number is not None

    def test_approve_rejects_non_pending_member(self, client, db):
        _create_user(db, email="admin@test.com", role="admin")
        _, active = _create_user(db, email="active@test.com", status="active")
        _login(client, "admin@test.com")

        response = client.post(f"/api/v1/members/{active.id}/approve")

        assert response.status_code == 400

    def test_reject_cancels_member_and_disables_login(self, client, db):
        _create_user(db, email="admin@test.com", role="admin")
        rejected_user, pending = _create_user(db, email="pending@test.com", status="pending")
        _login(client, "admin@test.com")

        response = client.post(
            f"/api/v1/members/{pending.id}/reject", json={"reason": "Not eligible"}
        )

        assert response.status_code == 200
        db.refresh(pending)
        db.refresh(rejected_user)
        assert pending.status == "cancelled"
        assert pending.status_reason == "Not eligible"
        assert pending.member_number is None
        assert rejected_user.is_active is False

    def test_approve_requires_admin(self, client, db):
        _create_user(db, email="member@test.com")
        _, pending = _create_user(db, email="pending@test.com", status="pending")
        _login(client, "member@test.com")

        response = client.post(f"/api/v1/members/{pending.id}/approve")

        assert response.status_code == 403

    def test_pending_members_are_listable_by_status(self, client, db):
        _create_user(db, email="admin@test.com", role="admin")
        _create_user(db, email="pending@test.com", status="pending")
        _login(client, "admin@test.com")

        response = client.get("/api/v1/members/?status=pending")

        assert response.status_code == 200
        emails = [m["person"]["email"] for m in response.json()["items"]]
        assert "pending@test.com" in emails


class TestPendingMemberGate:
    def test_pending_member_can_log_in_and_read_own_status(self, client, db):
        _create_user(db, email="pending@test.com", status="pending")

        _login(client, "pending@test.com")
        response = client.get("/api/v1/auth/me")

        assert response.status_code == 200
        assert response.json()["member_status"] == "pending"

    def test_pending_member_is_blocked_from_feature_routers(self, client, db):
        _create_user(db, email="pending@test.com", status="pending")
        _login(client, "pending@test.com")

        response = client.get("/api/v1/activities/")

        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "pending_approval"

    def test_active_member_passes_the_gate(self, client, db):
        _create_user(db, email="active@test.com", status="active")
        _login(client, "active@test.com")

        response = client.get("/api/v1/activities/")

        assert response.status_code == 200

    def test_admin_passes_the_gate_regardless_of_member_status(self, client, db):
        _create_user(db, email="admin@test.com", role="admin", status="pending")
        _login(client, "admin@test.com")

        response = client.get("/api/v1/activities/")

        assert response.status_code == 200

    def test_gate_opens_after_approval(self, client, db):
        _create_user(db, email="admin@test.com", role="admin")
        _, pending = _create_user(db, email="pending@test.com", status="pending")

        _login(client, "admin@test.com")
        client.post(f"/api/v1/members/{pending.id}/approve")

        _login(client, "pending@test.com")
        response = client.get("/api/v1/activities/")

        assert response.status_code == 200