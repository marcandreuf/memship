"""The way back when sign-in requires a confirmed address.

Requiring confirmation closes a real hole, but it also means an account that
never confirmed cannot get in — and the self-service route needs a working mail
transport, which is exactly what tends to be broken when this comes up. Without
this command the remedy is raw SQL against production.
"""

import pytest

from app.cli import verify_email as cli
from app.domains.auth.models import User
from app.domains.persons.models import Person


def _user(db, email, verified=False):
    person = Person(first_name="V", last_name="E", email=email)
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=email,
        password_hash="x",
        role="member",
        is_active=True,
        email_verified=verified,
    )
    db.add(user)
    db.flush()
    return user


class TestListing:
    def test_lists_only_the_unconfirmed(self, db):
        _user(db, "yes@examplee6e3b1.com", verified=True)
        _user(db, "no@examplee6e3b1.com", verified=False)

        pending = [u.email for u in cli._unverified(db)]

        assert "no@examplee6e3b1.com" in pending
        assert "yes@examplee6e3b1.com" not in pending

    def test_a_null_counts_as_unconfirmed(self, db):
        """The column is nullable and predates the flag being used."""
        user = _user(db, "null@examplee6e3b1.com", verified=False)
        user.email_verified = None
        db.flush()

        assert "null@examplee6e3b1.com" in [u.email for u in cli._unverified(db)]


class TestConfirming:
    def test_confirming_sets_the_flag_and_the_timestamp(self, db):
        user = _user(db, "one@examplee6e3b1.com")
        assert user.email_verified_at is None

        cli._confirm(user)
        db.flush()

        assert user.email_verified is True
        assert user.email_verified_at is not None

    def test_a_confirmed_user_can_sign_in(self, client, db):
        """The whole point — end to end through the login endpoint."""
        from app.core.security.password import hash_password

        email = "signin@examplee6e3b1.com"
        user = _user(db, email)
        user.password_hash = hash_password("Sup3rSecret!")
        db.flush()

        before = client.post(
            "/api/v1/auth/login", json={"email": email, "password": "Sup3rSecret!"}
        )
        assert before.status_code == 403, "unconfirmed should not get in"

        cli._confirm(user)
        db.flush()

        after = client.post(
            "/api/v1/auth/login", json={"email": email, "password": "Sup3rSecret!"}
        )
        assert after.status_code == 200, after.text

    def test_confirming_does_not_touch_anyone_else(self, db):
        target = _user(db, "target@examplee6e3b1.com")
        bystander = _user(db, "bystander@examplee6e3b1.com")

        cli._confirm(target)
        db.flush()

        assert bystander.email_verified is False
