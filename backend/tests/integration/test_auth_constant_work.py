"""The constant-work half of #102, where it needs a database.

`authenticate_user` answers "no such account", "SSO-only account" and "wrong
password" identically to its caller, which only stays true while all three cost
the same. Timing is not asserted — a wall-clock threshold fails on a loaded CI
box and teaches everyone to rerun it — but the property it follows from is.
"""

import pytest

from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.auth.service import authenticate_user
from app.domains.persons.models import Person


def _person(db, email, first="Test", last="User"):
    person = Person(first_name=first, last_name=last, email=email)
    db.add(person)
    db.flush()
    return person


class TestAuthenticateUserSpendsEvenly:
    @pytest.fixture
    def spent(self, monkeypatch):
        calls: list[str] = []
        monkeypatch.setattr(
            "app.domains.auth.service.spend_verify_work", lambda p: calls.append(p)
        )
        return calls

    def test_unknown_address_spends_the_work(self, db, spent):
        assert authenticate_user(db, "nobody@examplee6e3b1.com", "password123") is None
        assert spent == ["password123"]

    def test_sso_only_account_spends_the_work(self, db, spent):
        person = _person(db, "sso@examplee6e3b1.com", first="Sso", last="Only")
        db.add(
            User(
                person_id=person.id,
                email="sso@examplee6e3b1.com",
                password_hash=None,
                is_active=True,
                email_verified=True,
            )
        )
        db.flush()

        assert authenticate_user(db, "sso@examplee6e3b1.com", "password123") is None
        assert spent == ["password123"]

    def test_a_wrong_password_does_not_spend_it_twice(self, db, spent):
        """That path already ran argon2 for real. A decoy on top would make it
        the slowest of the three and reinstate the difference the other way."""
        person = _person(db, "real@examplee6e3b1.com", first="Real")
        db.add(
            User(
                person_id=person.id,
                email="real@examplee6e3b1.com",
                password_hash=hash_password("password123"),
                is_active=True,
                email_verified=True,
            )
        )
        db.flush()

        assert authenticate_user(db, "real@examplee6e3b1.com", "wrong-password") is None
        assert spent == []

    def test_the_right_password_still_authenticates(self, db, spent):
        person = _person(db, "good@examplee6e3b1.com", first="Good")
        db.add(
            User(
                person_id=person.id,
                email="good@examplee6e3b1.com",
                password_hash=hash_password("password123"),
                is_active=True,
                email_verified=True,
            )
        )
        db.flush()

        user = authenticate_user(db, "good@examplee6e3b1.com", "password123")
        assert user is not None
        assert spent == []
