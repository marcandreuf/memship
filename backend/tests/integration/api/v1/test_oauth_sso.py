"""Integration tests for SSO identity resolution (v1.3.0)."""

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


class TestAppleClientSecret:
    """Apple has no static secret — it is an ES256 JWT signed with the .p8 key."""

    # A throwaway P-256 key generated for this test only.
    PRIVATE_KEY = (
        "-----BEGIN PRIVATE KEY-----\n"
        "MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgevZzL1gdAFr88hb2\n"
        "OF/2NxApJCzGCEDdfSp6VQO30hyhRANCAAQRWz+jn65BtOMvdyHKcvjBeBSDZH2r\n"
        "1RTwjmYSi9R/zpBnuQ4EiMnCqfMPWiZqB4QdbAd0E7oH50VpuZ1P087G\n"
        "-----END PRIVATE KEY-----"
    )

    def _configure(self, monkeypatch, private_key=None):
        from app.core.config import settings

        monkeypatch.setattr(settings, "APPLE_CLIENT_ID", "com.example.memship", raising=False)
        monkeypatch.setattr(settings, "APPLE_TEAM_ID", "TEAM123456", raising=False)
        monkeypatch.setattr(settings, "APPLE_KEY_ID", "KEY1234567", raising=False)
        monkeypatch.setattr(
            settings, "APPLE_PRIVATE_KEY", private_key or self.PRIVATE_KEY, raising=False
        )

    def test_builds_an_es256_jwt_with_the_expected_claims(self, monkeypatch):
        import jwt as pyjwt

        from app.core.security.oauth import APPLE_AUDIENCE, build_apple_client_secret
        from app.domains.auth.sso_config import _resolve_provider

        self._configure(monkeypatch)

        # No DB node → the Apple credentials resolve from the patched env vars.
        secret = build_apple_client_secret(_resolve_provider("apple", {}))

        header = pyjwt.get_unverified_header(secret)
        assert header["alg"] == "ES256"
        assert header["kid"] == "KEY1234567"

        claims = pyjwt.decode(
            secret,
            options={"verify_signature": False},
            audience=APPLE_AUDIENCE,
        )
        assert claims["iss"] == "TEAM123456"
        # `sub` must be the Services ID, not the team.
        assert claims["sub"] == "com.example.memship"
        assert claims["aud"] == APPLE_AUDIENCE
        assert claims["exp"] > claims["iat"]

    def test_accepts_a_key_with_escaped_newlines(self, monkeypatch):
        """Env vars usually carry the .p8 as a single line with literal \\n."""
        from app.core.security.oauth import build_apple_client_secret
        from app.domains.auth.sso_config import _resolve_provider

        self._configure(monkeypatch, private_key=self.PRIVATE_KEY.replace("\n", "\\n"))

        assert build_apple_client_secret(_resolve_provider("apple", {}))

    def test_apple_sso_stays_disabled_until_every_field_is_set(self, monkeypatch):
        from app.core.config import settings

        self._configure(monkeypatch)
        assert settings.apple_sso_enabled is True

        monkeypatch.setattr(settings, "APPLE_KEY_ID", "", raising=False)
        assert settings.apple_sso_enabled is False


class TestProviderRegistration:
    """Guards two Apple settings whose absence fails silently rather than loudly."""

    def test_apple_requests_the_openid_scope(self):
        # authlib only generates a nonce — and so only parses the returned
        # id_token into `userinfo` — when the scope asks for `openid`. Drop it
        # and every Apple sign-in completes with an empty profile.
        from app.core.security.oauth import APPLE_CLIENT_KWARGS

        assert "openid" in APPLE_CLIENT_KWARGS["scope"].split()

    def test_apple_uses_form_post(self):
        # Apple only returns the email and name claims with form_post.
        from app.core.security.oauth import APPLE_CLIENT_KWARGS

        assert APPLE_CLIENT_KWARGS["response_mode"] == "form_post"


class TestAppleFormPostName:
    """Apple posts the profile name back only on the first authorization."""

    @pytest.mark.anyio
    async def test_reads_first_and_last_name_from_the_user_field(self):
        from app.api.v1.endpoints.auth import _apple_form_name

        request = _fake_form_request(
            {"user": '{"name": {"firstName": "Ada", "lastName": "Lovelace"}}'}
        )

        assert await _apple_form_name(request) == ("Ada", "Lovelace")

    @pytest.mark.anyio
    async def test_returns_blanks_when_apple_omits_the_name(self):
        from app.api.v1.endpoints.auth import _apple_form_name

        # Every sign-in after the first has no `user` field.
        assert await _apple_form_name(_fake_form_request({})) == ("", "")

    @pytest.mark.anyio
    async def test_malformed_user_payload_does_not_raise(self):
        from app.api.v1.endpoints.auth import _apple_form_name

        request = _fake_form_request({"user": "not-json"})

        assert await _apple_form_name(request) == ("", "")


class _FakeForm(dict):
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _fake_form_request(fields: dict):
    class _Request:
        async def form(self):
            return _FakeForm(fields)

    return _Request()


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

    def test_apple_callback_accepts_post(self, client):
        """Apple uses response_mode=form_post, so the callback must allow POST."""
        response = client.post(
            "/api/v1/auth/oauth/apple/callback", data={"code": "x", "state": "y"}
        )
        # 404 because Apple is unconfigured here — a 405 would mean the route
        # rejects POST outright, which would break Apple in production.
        assert response.status_code == 404
