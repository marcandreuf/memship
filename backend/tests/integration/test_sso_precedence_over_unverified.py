"""A provider-verified sign-in outranks an unverified account (#644).

An unverified account is not a valid account: sign-in is refused until the
address is confirmed, so nobody ever proved they hold it. It still occupies the
address in ``users.email``, which is unique, and SSO resolution used to treat it
as an existing account to link to, marking it verified on the way. The person
who actually controls the mailbox then inherited whatever that abandoned sign-up
left behind, including its password.

So the provider's claim wins: the unverified account's **party** is deleted,
with everything the cascade reaches, and a fresh account is created for the
provider identity.

Three things here are easy to get wrong and each has a test:

* deleting the ``users`` row rather than the party would orphan the Person, the
  Party and the pending Member, leave the address on the party row, and give the
  replacement a second set of all three;
* creating before deleting collides with the unique index on the address;
* discarding the account and *then* finding registration closed would destroy
  an account and refuse the replacement, so the settings are read first.

Linking into an account that is verified is unchanged, and has a test here so
that stays true.
"""

import pytest

from app.core.security.password import hash_password
from app.domains.auth.models import User, UserIdentity
from app.domains.auth.oauth_service import (
    OAuthProfile,
    RegistrationClosedError,
    find_or_create_from_oauth,
)
from app.domains.audit.models import AuditLog
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Party, Person


def _profile(email, subject="sub-1", provider="google"):
    return OAuthProfile(
        provider=provider,
        subject=subject,
        email=email,
        email_verified=True,
        first_name="Provider",
        last_name="Person",
    )


@pytest.fixture
def org(db):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(
            id=1, name="Test Club", locale="es", timezone="Europe/Madrid",
            currency="EUR", date_format="DD/MM/YYYY",
        )
        db.add(org)
    org.features = {**(org.features or {}), "public_registration": True}
    db.flush()
    return org


@pytest.fixture
def membership_type(db):
    mt = db.query(MembershipType).filter(MembershipType.is_default == True).first()
    if not mt:
        mt = MembershipType(
            name="SSO Default", slug="sso-default", base_price=0,
            billing_frequency="annual", is_default=True,
        )
        db.add(mt)
        db.flush()
    return mt


def _self_registration(db, membership_type, email, *, verified):
    """What `register_user` leaves behind: person, party, user, pending member."""
    person = Person(first_name="Squatted", last_name="Signup", email=email)
    db.add(person)
    db.flush()
    user = User(
        party_id=person.party_id, email=email,
        password_hash=hash_password("password123"), role="member",
        is_active=True, email_verified=verified,
    )
    db.add(user)
    db.flush()
    member = Member(
        party_id=person.party_id, membership_type_id=membership_type.id,
        member_number=None, status="pending",
    )
    db.add(member)
    db.flush()
    return user, member


class TestUnverifiedAccountIsReplaced:
    def test_the_provider_gets_a_brand_new_account(self, db, org, membership_type):
        email = "sso-replace@example.com"
        old, _member = _self_registration(db, membership_type, email, verified=False)
        old_user_id, old_party_id = old.id, old.party_id

        user, created = find_or_create_from_oauth(db, _profile(email))
        db.flush()

        assert created is True
        assert user.id != old_user_id
        assert user.party_id != old_party_id
        assert user.email == email
        assert user.email_verified is True
        # The replacement signs in through the provider only. Inheriting the
        # abandoned sign-up's password is the whole defect.
        assert user.password_hash is None

    def test_the_whole_party_goes_not_just_the_login(
        self, db, org, membership_type
    ):
        email = "sso-cascade@example.com"
        old, old_member = _self_registration(db, membership_type, email, verified=False)
        old_party_id, old_member_id = old.party_id, old_member.id

        find_or_create_from_oauth(db, _profile(email))
        db.flush()

        assert db.query(Party).filter(Party.id == old_party_id).first() is None
        assert db.query(Person).filter(Person.party_id == old_party_id).first() is None
        assert db.query(Member).filter(Member.id == old_member_id).first() is None
        assert db.query(User).filter(User.party_id == old_party_id).first() is None

    def test_exactly_one_account_holds_the_address_afterwards(
        self, db, org, membership_type
    ):
        """Delete before insert, or the unique index on the address rejects it.

        Counting accounts alone would pass on the old behaviour too, which
        linked rather than replaced, so this also asserts the survivor is the
        replacement and that it brought exactly one party and one member with
        it.
        """
        email = "sso-unique@example.com"
        old, _ = _self_registration(db, membership_type, email, verified=False)
        old_user_id = old.id

        user, _created = find_or_create_from_oauth(db, _profile(email))
        db.flush()

        holders = db.query(User).filter(User.email == email).all()
        assert len(holders) == 1
        assert holders[0].id == user.id != old_user_id
        assert (
            db.query(Person).filter(Person.party_id == user.party_id).count() == 1
        )
        assert db.query(Member).filter(Member.party_id == user.party_id).count() == 1

    def test_the_deletion_is_audited(self, db, org, membership_type):
        email = "sso-audit@example.com"
        old, _ = _self_registration(db, membership_type, email, verified=False)
        old_party_id = old.party_id

        find_or_create_from_oauth(db, _profile(email))
        db.flush()

        entry = (
            db.query(AuditLog)
            .filter(
                AuditLog.table_name == "party",
                AuditLog.record_id == old_party_id,
                AuditLog.action == "delete",
            )
            .first()
        )
        assert entry is not None, "the cascade must not erase its own trace"
        assert entry.old_values is not None
        assert entry.old_values.get("email") == email

    def test_registration_closed_refuses_without_destroying_anything(
        self, db, org, membership_type
    ):
        """Settings are read before the delete, not after.

        Discarding the account and then refusing to create its replacement
        would leave the person with neither.
        """
        email = "sso-closed@example.com"
        old, _ = _self_registration(db, membership_type, email, verified=False)
        old_party_id = old.party_id
        org.features = {**(org.features or {}), "public_registration": False}
        db.flush()

        with pytest.raises(RegistrationClosedError):
            find_or_create_from_oauth(db, _profile(email))

        assert db.query(Party).filter(Party.id == old_party_id).first() is not None
        assert db.query(User).filter(User.email == email).count() == 1


class TestVerifiedAccountStillLinks:
    def test_a_verified_account_is_linked_not_replaced(
        self, db, org, membership_type
    ):
        """The normal path, and the one that must not change."""
        email = "sso-link@example.com"
        existing, _ = _self_registration(db, membership_type, email, verified=True)
        existing_id, existing_party = existing.id, existing.party_id

        user, created = find_or_create_from_oauth(db, _profile(email, subject="sub-link"))
        db.flush()

        assert created is False
        assert user.id == existing_id
        assert user.party_id == existing_party
        # Their password still works: this account was always theirs.
        assert user.password_hash is not None
        assert (
            db.query(UserIdentity)
            .filter(UserIdentity.user_id == existing_id)
            .count()
            == 1
        )
