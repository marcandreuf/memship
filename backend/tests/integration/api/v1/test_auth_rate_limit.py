"""The four unauthenticated auth endpoints are bounded.

`POST /auth/login` accepted unlimited password attempts, and the two endpoints
that mail an address chosen by an anonymous caller accepted unlimited requests
— so a member's mailbox could be flooded, and their pending reset token burned,
from outside.

The throttles are process-global, so every test here leans on the autouse
`_fresh_auth_throttles` fixture in tests/integration/conftest.py.
"""

import pytest

from app.core.security.password import hash_password
from app.core.security.rate_limit import (
    EMAIL_DISPATCH_BY_EMAIL,
    EMAIL_DISPATCH_BY_IP,
    LOGIN_BY_EMAIL,
    LOGIN_BY_IP,
    REGISTER_BY_IP,
)
from app.domains.auth.models import User
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person

PASSWORD = "correct-horse-battery"
# LoginRequest enforces min_length=8, and that rejection happens in validation,
# before the handler and so before the throttle. A guess short enough to fail
# there was never a viable guess, so the wrong passwords here are realistic ones.
WRONG = "wrong-password-guess"


@pytest.fixture
def org(db):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(
            id=1, name="Throttle Club", locale="es", timezone="Europe/Madrid",
            currency="EUR", date_format="DD/MM/YYYY", brand_color="#0083ad",
        )
        db.add(org)
    org.features = {"public_registration": True}
    db.flush()
    return org


@pytest.fixture
def account(db):
    person = Person(first_name="Throttle", last_name="Target", email="throttle@test.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email="throttle@test.com",
        password_hash=hash_password(PASSWORD),
        is_active=True,
        email_verified=True,
    )
    db.add(user)
    db.flush()
    return user


def _login(client, email, password, **kwargs):
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}, **kwargs
    )


class TestLoginIsBounded:
    def test_the_sixth_wrong_password_for_an_address_is_refused(
        self, client, db, account
    ):
        for _ in range(LOGIN_BY_EMAIL.limit):
            assert _login(client, account.email, WRONG).status_code == 401

        r = _login(client, account.email, WRONG)

        assert r.status_code == 429
        assert int(r.headers["Retry-After"]) > 0

    def test_the_right_password_is_refused_too_once_the_window_is_spent(
        self, client, db, account
    ):
        """The point of the limit: an attacker must not learn that the guess
        they just made was the correct one."""
        for _ in range(LOGIN_BY_EMAIL.limit):
            _login(client, account.email, WRONG)

        assert _login(client, account.email, PASSWORD).status_code == 429

    def test_a_successful_login_clears_the_addresss_failures(
        self, client, db, account
    ):
        for _ in range(LOGIN_BY_EMAIL.limit - 1):
            _login(client, account.email, WRONG)

        assert _login(client, account.email, PASSWORD).status_code == 200

        for _ in range(LOGIN_BY_EMAIL.limit - 1):
            assert _login(client, account.email, WRONG).status_code == 401

    def test_a_successful_login_is_not_counted_at_all(self, client, db, account):
        """Signing in from several devices is not an attack."""
        for _ in range(LOGIN_BY_EMAIL.limit + 3):
            assert _login(client, account.email, PASSWORD).status_code == 200

    def test_casing_cannot_split_the_count(self, client, db, account):
        for i in range(LOGIN_BY_EMAIL.limit):
            variant = account.email.upper() if i % 2 else account.email
            assert _login(client, variant, WRONG).status_code == 401

        assert _login(client, "THROTTLE@TEST.COM", WRONG).status_code == 429

    def test_one_address_being_blocked_does_not_block_another(self, client, db, account):
        for _ in range(LOGIN_BY_EMAIL.limit):
            _login(client, account.email, WRONG)

        r = _login(client, "someone-else@test.com", WRONG)

        assert r.status_code == 401

    def test_a_spray_across_addresses_is_bounded_by_the_source(self, client, db):
        """Each address stays under its own limit, so only the per-source
        window catches this."""
        for i in range(LOGIN_BY_IP.limit):
            assert _login(client, f"spray{i}@test.com", WRONG).status_code == 401

        assert _login(client, "spray-last@test.com", WRONG).status_code == 429

    def test_the_source_is_read_from_the_rightmost_forwarded_hop(self, client, db):
        """Behind Caddy every request arrives from the same container address,
        so the per-source limit is only worth anything if the proxy header is
        what gets keyed on."""
        for i in range(LOGIN_BY_IP.limit):
            r = _login(
                client, f"fwd{i}@test.com", WRONG,
                headers={"X-Forwarded-For": "198.51.100.7"},
            )
            assert r.status_code == 401

        blocked = _login(
            client, "fwd-last@test.com", WRONG,
            headers={"X-Forwarded-For": "198.51.100.7"},
        )
        other = _login(
            client, "fwd-other@test.com", WRONG,
            headers={"X-Forwarded-For": "198.51.100.8"},
        )

        assert blocked.status_code == 429
        assert other.status_code == 401


class TestMailDispatchIsBounded:
    def test_password_reset_requests_for_one_address_are_capped(self, client, db, account):
        for _ in range(EMAIL_DISPATCH_BY_EMAIL.limit):
            r = client.post(
                "/api/v1/auth/password-reset-request", json={"email": account.email}
            )
            assert r.status_code == 200

        r = client.post(
            "/api/v1/auth/password-reset-request", json={"email": account.email}
        )

        assert r.status_code == 429

    def test_an_unknown_address_is_capped_the_same_way(self, client, db):
        """The endpoint answers the same generic message either way, so the
        throttle must not treat the two differently — that would turn the
        response code into the disclosure the generic message avoids."""
        for _ in range(EMAIL_DISPATCH_BY_EMAIL.limit):
            r = client.post(
                "/api/v1/auth/password-reset-request", json={"email": "nobody@test.com"}
            )
            assert r.status_code == 200

        r = client.post(
            "/api/v1/auth/password-reset-request", json={"email": "nobody@test.com"}
        )

        assert r.status_code == 429

    def test_resend_verification_shares_the_budget_with_password_reset(
        self, client, db, account
    ):
        """Both mail the same address on an anonymous request, so switching
        endpoint must not buy a fresh allowance."""
        for _ in range(EMAIL_DISPATCH_BY_EMAIL.limit):
            client.post(
                "/api/v1/auth/password-reset-request", json={"email": account.email}
            )

        r = client.post(
            "/api/v1/auth/resend-verification", json={"email": account.email}
        )

        assert r.status_code == 429

    def test_the_source_is_capped_across_different_addresses(self, client, db):
        for i in range(EMAIL_DISPATCH_BY_IP.limit):
            r = client.post(
                "/api/v1/auth/password-reset-request", json={"email": f"m{i}@test.com"}
            )
            assert r.status_code == 200

        r = client.post(
            "/api/v1/auth/password-reset-request", json={"email": "m-last@test.com"}
        )

        assert r.status_code == 429


class TestRegistrationIsBounded:
    def _register(self, client, i):
        return client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "New",
                "last_name": "Member",
                "email": f"signup{i}@test.com",
                "password": "a-long-enough-password",
            },
        )

    def test_signups_from_one_source_are_capped(self, client, db, org):
        for i in range(REGISTER_BY_IP.limit):
            assert self._register(client, i).status_code == 201

        assert self._register(client, 99).status_code == 429

    def test_a_rejected_signup_still_spends_the_budget(self, client, db, org):
        """Otherwise turning public registration off, or colliding on an
        existing address, would make the endpoint free to hammer."""
        org.features = {"public_registration": False}
        db.flush()

        for i in range(REGISTER_BY_IP.limit):
            assert self._register(client, i).status_code == 403

        assert self._register(client, 99).status_code == 429
