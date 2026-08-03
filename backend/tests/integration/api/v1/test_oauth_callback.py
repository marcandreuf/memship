"""Integration tests for the OAuth callback endpoint.

``test_oauth_sso.py`` covers identity resolution by calling
``find_or_create_from_oauth`` directly, and covers the callback route only in
its unconfigured-provider form, which returns 404 before any authentication
runs. Everything the endpoint itself decides once the provider *is* configured
was therefore unexercised.

That matters most for two gates:

    if not user.is_active:  -> account_disabled
    if user.is_locked:      -> account_locked

Neither is enforced anywhere else. ``find_or_create_from_oauth`` resolves a user
by email without filtering on either flag, so the endpoint is the only thing
stopping a disabled or locked account signing in through a provider. The
password path already asserts the locked case (``test_auth.py``); this closes
the same hole on the SSO path.

These stub the authlib client at ``get_provider``, which is the seam the
endpoint imports at module level.
"""

import pytest

from app.core.security.password import hash_password
from app.domains.auth.models import User, UserIdentity
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person

GOOGLE_CALLBACK = "/api/v1/auth/oauth/google/callback?code=x&state=y"
APPLE_CALLBACK = "/api/v1/auth/oauth/apple/callback"

CLAIMS = {
    "sub": "google-sub-1",
    "email": "sso@test.com",
    "email_verified": True,
    "given_name": "Sso",
    "family_name": "User",
}


class _FakeOAuthClient:
    """Stands in for the authlib client the provider registry builds.

    Only ``authorize_access_token`` is reached on the callback path. Raising
    from it reproduces every way authlib rejects a callback — denied consent, a
    replayed or expired code, a failed state check, a bad id_token signature —
    all of which the endpoint funnels into one redirect.
    """

    def __init__(self, claims=None, raises=None):
        self._claims = claims
        self._raises = raises

    async def authorize_access_token(self, request):
        if self._raises is not None:
            raise self._raises
        return {"userinfo": self._claims}


@pytest.fixture
def stub_provider(monkeypatch):
    def _install(claims=None, raises=None):
        client = _FakeOAuthClient(claims=claims, raises=raises)
        monkeypatch.setattr(
            "app.api.v1.endpoints.auth.get_provider",
            lambda name, resolved: client,
        )
        return client

    return _install


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


def _password_user(db, email="sso@test.com", **flags):
    person = Person(first_name="Existing", last_name="User", email=email)
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=email,
        password_hash=hash_password("password123"),
        role="member",
        is_active=flags.get("is_active", True),
        is_locked=flags.get("is_locked", False),
        email_verified=True,
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


def _location(response):
    assert response.status_code in (302, 303, 307), response.status_code
    return response.headers["location"]


# --- Provider rejected the sign-in ----------------------------------------


def test_token_exchange_failure_redirects_to_login(client, db, stub_provider):
    """Denied consent, replayed code, bad state or bad id_token all land here.

    The endpoint deliberately collapses them into one opaque error rather than
    echoing the provider's message, so this also pins that nothing leaks.
    """
    stub_provider(raises=RuntimeError("mismatching_state: CSRF Warning"))

    response = client.get(GOOGLE_CALLBACK, follow_redirects=False)

    location = _location(response)
    assert "error=sso_failed" in location
    assert "CSRF" not in location
    assert "mismatching_state" not in location
    assert db.query(User).count() == 0


def test_claims_without_subject_are_refused(client, db, stub_provider):
    stub_provider(claims={"email": "sso@test.com", "email_verified": True})

    response = client.get(GOOGLE_CALLBACK, follow_redirects=False)

    assert "error=sso_failed" in _location(response)
    assert db.query(User).count() == 0


def test_claims_without_email_are_refused(client, db, stub_provider):
    stub_provider(claims={"sub": "google-sub-1", "email_verified": True})

    response = client.get(GOOGLE_CALLBACK, follow_redirects=False)

    assert "error=sso_failed" in _location(response)
    assert db.query(User).count() == 0


def test_empty_userinfo_is_refused(client, db, stub_provider):
    """A token with no userinfo at all must not fall through as a sign-in."""
    stub_provider(claims=None)

    response = client.get(GOOGLE_CALLBACK, follow_redirects=False)

    assert "error=sso_failed" in _location(response)
    assert db.query(User).count() == 0


# --- Service refusals mapped to redirects ---------------------------------


def test_unverified_provider_email_redirects_not_500(client, db, stub_provider):
    """EmailNotVerifiedError must surface as a redirect, not an exception."""
    _password_user(db)
    stub_provider(claims={**CLAIMS, "email_verified": False})

    response = client.get(GOOGLE_CALLBACK, follow_redirects=False)

    assert "error=sso_email_unverified" in _location(response)
    assert db.query(UserIdentity).count() == 0


def test_closed_registration_redirects_not_500(client, db, stub_provider):
    _ensure_membership_type(db)
    _set_features(db, public_registration=False)
    stub_provider(claims=CLAIMS)

    response = client.get(GOOGLE_CALLBACK, follow_redirects=False)

    assert "error=registration_closed" in _location(response)
    assert db.query(User).count() == 0


# --- The gates that exist only here ---------------------------------------


def test_disabled_account_cannot_sign_in_through_sso(client, db, stub_provider):
    """A deactivated member must not get in via the provider.

    find_or_create_from_oauth resolves by email without checking is_active, so
    without the endpoint's gate this returns a session cookie.
    """
    _password_user(db, is_active=False)
    stub_provider(claims=CLAIMS)

    response = client.get(GOOGLE_CALLBACK, follow_redirects=False)

    assert "error=account_disabled" in _location(response)
    assert "access_token" not in response.headers.get("set-cookie", "")


def test_locked_account_cannot_sign_in_through_sso(client, db, stub_provider):
    """Mirror of test_auth.py's locked-password-login test, on the SSO path.

    Uses a returning identity — someone who signed in before and was locked
    afterwards — which is how this actually happens.
    """
    user = _password_user(db)
    db.add(
        UserIdentity(
            user_id=user.id,
            provider="google",
            provider_subject="google-sub-1",
            email=user.email,
        )
    )
    user.is_locked = True
    db.flush()
    stub_provider(claims=CLAIMS)

    response = client.get(GOOGLE_CALLBACK, follow_redirects=False)

    assert "error=account_locked" in _location(response)
    assert "access_token" not in response.headers.get("set-cookie", "")


# --- The success path ------------------------------------------------------


def test_successful_signin_issues_a_session_cookie(client, db, stub_provider):
    _ensure_membership_type(db)
    stub_provider(claims=CLAIMS)

    response = client.get(GOOGLE_CALLBACK, follow_redirects=False)

    location = _location(response)
    assert "/dashboard" in location
    assert "error=" not in location

    cookie = response.headers.get("set-cookie", "")
    assert "access_token=" in cookie
    assert "HttpOnly" in cookie

    user = db.query(User).filter(User.email == "sso@test.com").one()
    assert user.password_hash is None
    assert user.last_login_at is not None


def test_returning_user_signs_in_without_creating_a_second_account(
    client, db, stub_provider
):
    _ensure_membership_type(db)
    stub_provider(claims=CLAIMS)

    client.get(GOOGLE_CALLBACK, follow_redirects=False)
    client.get(GOOGLE_CALLBACK, follow_redirects=False)

    assert db.query(User).filter(User.email == "sso@test.com").count() == 1
    assert db.query(UserIdentity).count() == 1


def test_pending_member_still_gets_a_session(client, db, stub_provider):
    """The portal shows an awaiting-approval screen, so the sign-in must work."""
    _ensure_membership_type(db)
    _set_features(db, registration_requires_approval=True)
    stub_provider(claims=CLAIMS)

    response = client.get(GOOGLE_CALLBACK, follow_redirects=False)

    assert "/dashboard" in _location(response)
    assert "access_token=" in response.headers.get("set-cookie", "")

    user = db.query(User).filter(User.email == "sso@test.com").one()
    member = db.query(Member).filter(Member.user_id == user.id).one()
    assert member.status == "pending"


# --- Apple sends email_verified as a string --------------------------------


def test_apple_string_true_is_treated_as_verified(client, db, stub_provider):
    """Apple sends "true"/"false" as strings, not booleans."""
    _ensure_membership_type(db)
    stub_provider(
        claims={**CLAIMS, "sub": "apple-sub-1", "email_verified": "true"}
    )

    response = client.post(APPLE_CALLBACK, data={"code": "x"}, follow_redirects=False)

    assert "/dashboard" in _location(response)
    assert db.query(User).filter(User.email == "sso@test.com").count() == 1


def test_apple_string_false_is_not_truthy(client, db, stub_provider):
    """The coercion earns its keep here: bool("false") is True.

    Without it, Apple reporting an unverified address would read as verified
    and allow linking into an existing account by email.
    """
    _password_user(db)
    stub_provider(
        claims={**CLAIMS, "sub": "apple-sub-1", "email_verified": "false"}
    )

    response = client.post(APPLE_CALLBACK, data={"code": "x"}, follow_redirects=False)

    assert "error=sso_email_unverified" in _location(response)
    assert db.query(UserIdentity).count() == 0
