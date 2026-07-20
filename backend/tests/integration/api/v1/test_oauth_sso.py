"""Integration tests for SSO identity resolution (v1.2.1)."""

import pytest

from app.core.security.password import hash_password
from app.domains.auth.models import User, UserIdentity
from app.domains.auth.oauth_service import (
    EmailNotVerifiedError,
    OAuthProfile,
    RegistrationClosedError,
    find_or_create_from_oauth,
)
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


def _profile(**overrides) -> OAuthProfile:
    base = dict(
        provider="google",
        subject="google-sub-1",
        email="sso@test.com",
        email_verified=True,
        first_name="Sso",
        last_name="User",
    )
    base.update(overrides)
    return OAuthProfile(**base)


def _ensure_membership_type(db):
    mt = db.query(MembershipType).first()
    if not mt:
        mt = MembershipType(name="General", slug="general", is_active=True)
        db.add(mt)
        db.flush()
    return mt


def _set_features(db, **flags):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(id=1, name="Test Club")
        db.add(org)
        db.flush()
    org.features = {**(org.features or {}), **flags}
    db.flush()


def _create_password_user(db, email, email_verified=True):
    person = Person(first_name="Existing", last_name="User", email=email)
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=email,
        password_hash=hash_password("password123"),
        role="member",
        is_active=True,
        email_verified=email_verified,
    )
    db.add(user)
    db.flush()
    mt = _ensure_membership_type(db)
    db.add(
        Member(
            person_id=person.id,
            user_id=user.id,
            membership_type_id=mt.id,
            member_number="M-9001",
            status="active",
        )
    )
    db.flush()
    return user


class TestFirstTimeSsoSignIn:
    def test_creates_pending_member_with_verified_email_and_no_password(self, db):
        _ensure_membership_type(db)

        user, created = find_or_create_from_oauth(db, _profile())

        assert created is True
        assert user.email == "sso@test.com"
        assert user.email_verified is True
        # SSO-only account: nothing to log in with on the password path.
        assert user.password_hash is None

        member = db.query(Member).filter(Member.user_id == user.id).first()
        assert member.status == "pending"
        assert member.member_number is None

    def test_links_the_identity_to_the_new_user(self, db):
        _ensure_membership_type(db)

        user, _ = find_or_create_from_oauth(db, _profile())

        identity = (
            db.query(UserIdentity).filter(UserIdentity.user_id == user.id).one()
        )
        assert identity.provider == "google"
        assert identity.provider_subject == "google-sub-1"

    def test_activates_immediately_when_approval_not_required(self, db):
        _ensure_membership_type(db)
        _set_features(db, registration_requires_approval=False)

        user, _ = find_or_create_from_oauth(db, _profile())

        member = db.query(Member).filter(Member.user_id == user.id).first()
        assert member.status == "active"
        assert member.member_number is not None

    def test_rejected_when_public_registration_is_disabled(self, db):
        _ensure_membership_type(db)
        _set_features(db, public_registration=False)

        with pytest.raises(RegistrationClosedError):
            find_or_create_from_oauth(db, _profile())

    def test_existing_user_can_still_sign_in_when_registration_is_closed(self, db):
        _create_password_user(db, "sso@test.com")
        _set_features(db, public_registration=False)

        # Closing sign-ups must not lock out members who already have accounts.
        user, created = find_or_create_from_oauth(db, _profile())

        assert created is False
        assert user.email == "sso@test.com"


class TestReturningSsoSignIn:
    def test_same_subject_resolves_to_the_same_user(self, db):
        _ensure_membership_type(db)
        first, _ = find_or_create_from_oauth(db, _profile())

        second, created = find_or_create_from_oauth(db, _profile())

        assert created is False
        assert second.id == first.id
        assert db.query(UserIdentity).count() == 1

    def test_subject_wins_over_a_changed_email(self, db):
        _ensure_membership_type(db)
        first, _ = find_or_create_from_oauth(db, _profile())

        # Google account keeps its `sub` but the address changed.
        second, created = find_or_create_from_oauth(
            db, _profile(email="renamed@test.com")
        )

        assert created is False
        assert second.id == first.id


class TestLinkingToAnExistingAccount:
    def test_links_to_a_user_registered_with_a_password(self, db):
        existing = _create_password_user(db, "sso@test.com")

        user, created = find_or_create_from_oauth(db, _profile())

        assert created is False
        assert user.id == existing.id
        # Still has the password: the account now has two ways in.
        assert user.password_hash is not None
        identity = db.query(UserIdentity).filter(UserIdentity.user_id == user.id).one()
        assert identity.provider_subject == "google-sub-1"

    def test_linking_confirms_a_previously_unverified_email(self, db):
        existing = _create_password_user(db, "sso@test.com", email_verified=False)
        existing.verification_token = "pending-token"
        db.flush()

        user, _ = find_or_create_from_oauth(db, _profile())

        assert user.email_verified is True
        assert user.verification_token is None

    def test_unverified_provider_email_is_refused(self, db):
        """Guards the linking branch against account takeover."""
        _create_password_user(db, "sso@test.com")

        with pytest.raises(EmailNotVerifiedError):
            find_or_create_from_oauth(db, _profile(email_verified=False))

        assert db.query(UserIdentity).count() == 0


class TestSsoEndpoints:
    def test_providers_endpoint_reports_google_off_by_default(self, client):
        response = client.get("/api/v1/auth/sso/providers")

        assert response.status_code == 200
        # No GOOGLE_CLIENT_ID configured in the test environment.
        assert response.json()["google"] is False

    def test_login_route_404s_when_provider_not_configured(self, client):
        response = client.get("/api/v1/auth/oauth/google/login")
        assert response.status_code == 404

    def test_callback_404s_when_provider_not_configured(self, client):
        response = client.get("/api/v1/auth/oauth/google/callback?code=x&state=y")
        assert response.status_code == 404

    def test_unknown_provider_404s(self, client):
        response = client.get("/api/v1/auth/oauth/facebook/login")
        assert response.status_code == 404
