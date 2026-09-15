"""Addresses the CLI writes have to be reachable by the API that reads them.

The request schemas normalise every address on the way in (#191), so a lookup
can only ever match a stripped, lower-cased value. `app.cli.seed` builds
addresses from its arguments, its prompts and SEED_EMAIL_DOMAIN, none of which
pass through a schema.

Left un-normalised that is worse than the bug it came from: pre-#191 an account
created as `Admin@club.com` at least answered to that exact spelling, while
afterwards the schema lower-cases what it is sent and *no* spelling resolves to
the stored row. `--admin-email` is the documented first-setup command, and a
super admin is excluded from password reset, so there is no way back.
"""

import argparse

import pytest

from app.cli.seed import (
    _run_unattended,
    attach_login,
    create_staff_user,
    seed_address_types,
    seed_contact_types,
    seed_groups,
    seed_membership_types,
)
from app.core.permissions import SUPER_ADMIN_SLUG
from app.domains.auth.models import User, UserIdentity
from app.domains.auth.service import authenticate_user
from app.domains.persons.models import Person

PASSWORD = "correct horse battery staple"


def _base_install(db):
    seed_address_types(db)
    seed_contact_types(db)
    return seed_membership_types(db, seed_groups(db))


def _args(**overrides):
    defaults = {"reset_club_data": False, "admin_email": None, "club_name": None, "demo": False}
    return argparse.Namespace(**{**defaults, **overrides})


class TestTheUnattendedInstall:
    def test_a_capitalised_admin_address_is_stored_normalised(self, db, monkeypatch):
        membership_type = _base_install(db)
        monkeypatch.setenv("MEMSHIP_ADMIN_PASSWORD", PASSWORD)

        _run_unattended(db, membership_type, _args(admin_email="Admin.Owner@Example.ORG"))

        db.expire_all()
        user = db.query(User).filter_by(email="admin.owner@example.org").one()
        assert {r.slug for r in user.roles} == {SUPER_ADMIN_SLUG}
        # The person row is copied into `users.email` by `attach_login`, so it
        # has to agree too.
        assert user.person.email == "admin.owner@example.org"

    def test_the_account_it_creates_can_actually_sign_in(self, db, monkeypatch):
        """The failure this whole change is about.

        Asserting the stored value is not enough on its own — what broke was
        the round trip, and it broke for *every* spelling, so a test that signs
        in with the address as typed would have passed before the fix only by
        accident of case.
        """
        membership_type = _base_install(db)
        monkeypatch.setenv("MEMSHIP_ADMIN_PASSWORD", PASSWORD)

        _run_unattended(db, membership_type, _args(admin_email="Owner@Club.Example"))
        db.expire_all()

        # What the login form sends: it normalises before the request is made.
        assert authenticate_user(db, "owner@club.example", PASSWORD) is not None
        # And what an operator might type, which the schema normalises to the
        # same thing before the service ever sees it.
        assert authenticate_user(db, "Owner@Club.Example".lower(), PASSWORD) is not None

    def test_a_capitalised_address_resets_the_super_admin_it_matches(self, db, monkeypatch):
        """The recovery path, which is the only one a super admin has.

        `request_password_reset` refuses super admins, so this command is it.
        A lookup that missed the row would fall through to creating a second
        super admin — which the unique index on `lower(btrim(email))` then
        rejects, turning a password reset into a crash.
        """
        membership_type = _base_install(db)
        create_staff_user(
            db,
            {
                "first_name": "Owner",
                "last_name": "One",
                "email": "owner@examplee6e3b1.com",
                "password": "the original password",
            },
            SUPER_ADMIN_SLUG,
        )
        db.flush()
        existing = db.query(User).filter_by(email="owner@examplee6e3b1.com").one()
        before = existing.password_hash
        monkeypatch.setenv("MEMSHIP_ADMIN_PASSWORD", "a whole new password")

        _run_unattended(db, membership_type, _args(admin_email="Owner@ExampleE6E3B1.com"))

        db.expire_all()
        assert db.query(User).filter(User.email.ilike("owner@examplee6e3b1.com")).count() == 1
        assert db.query(User).filter_by(email="owner@examplee6e3b1.com").one().password_hash != before

    def test_it_still_refuses_an_address_belonging_to_a_non_super_admin(self, db, monkeypatch):
        """Normalising must not widen what the flag will reset.

        The refusal is a security property — resetting a member's password while
        reporting a super admin reset hands out someone else's credentials — and
        it now has to hold for a case variant of their address too, which
        previously missed the lookup and got refused only by accident.
        """
        membership_type = _base_install(db)
        person = Person(first_name="M", last_name="M", email="plain@examplee6e3b1.com")
        db.add(person)
        db.flush()
        member = User(
            person_id=person.id,
            email="plain@examplee6e3b1.com",
            password_hash="untouched",
            is_active=True,
        )
        db.add(member)
        db.flush()
        monkeypatch.setenv("MEMSHIP_ADMIN_PASSWORD", "a whole new password")

        with pytest.raises(SystemExit):
            _run_unattended(db, membership_type, _args(admin_email="Plain@ExampleE6E3B1.com"))

        assert member.password_hash == "untouched"


class TestTheModelValidators:
    """Where the rule is enforced, so a new writer cannot reintroduce this.

    The CLI is the caller that was missed twice — once when the three schema
    copies were found mid-fix, once when these paths were written off as
    admin-run and low-stakes. Normalising on the attribute covers whatever
    writes it next.
    """

    @pytest.mark.parametrize(
        "written,stored",
        [
            ("  Marc@Example.COM  ", "marc@example.com"),
            ("Marc@Example.com", "marc@example.com"),
            ("already@normal.com", "already@normal.com"),
        ],
    )
    def test_user_email_is_normalised_on_write(self, db, written, stored):
        person = Person(first_name="W", last_name="V", email=written)
        db.add(person)
        db.flush()
        user = User(person_id=person.id, email=written, password_hash="x", is_active=True)
        db.add(user)
        db.flush()

        assert user.email == stored
        assert person.email == stored

    def test_it_normalises_an_assignment_too_not_just_the_constructor(self, db):
        person = Person(first_name="A", last_name="S", email="before@example.com")
        db.add(person)
        db.flush()

        person.email = "  After@Example.COM "
        db.flush()

        assert person.email == "after@example.com"

    def test_a_none_stays_none(self, db):
        """`persons.email` is nullable — a member record without an address."""
        person = Person(first_name="N", last_name="N", email=None)
        db.add(person)
        db.flush()

        assert person.email is None

    def test_identity_email_is_normalised(self, db):
        """SSO writes this row; `OAuthProfile` normalises, but not every caller."""
        person = Person(first_name="I", last_name="D", email="sso@example.com")
        db.add(person)
        db.flush()
        user = User(person_id=person.id, email="sso@example.com", is_active=True)
        db.add(user)
        db.flush()

        identity = UserIdentity(
            user_id=user.id,
            provider="google",
            provider_subject="subject-1",
            email="SSO@Example.COM",
        )
        db.add(identity)
        db.flush()

        assert identity.email == "sso@example.com"

    def test_attach_login_copies_a_normalised_address(self, db):
        """Demo logins take their address from the person row.

        `attach_login` reads `person.email` straight into `users.email`, so the
        person validator is what keeps a login reachable on this path.
        """
        membership_type = _base_install(db)
        person = Person(first_name="D", last_name="L", email="Demo.Person@Example.ORG")
        db.add(person)
        db.flush()
        from app.domains.members.models import Member

        member = Member(person_id=person.id, membership_type_id=membership_type.id, status="active")
        db.add(member)
        db.flush()

        returned = attach_login(db, member, "a demo password")

        assert returned == "demo.person@example.org"
        assert db.query(User).filter_by(id=member.user_id).one().email == "demo.person@example.org"
