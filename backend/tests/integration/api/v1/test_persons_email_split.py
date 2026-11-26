"""``PUT /persons/{id}`` writes the mail address and leaves the login behind.

This is #98 again. That issue was the login address and the mail address drifting
apart: an update wrote one and not the other, so mail went to the corrected
address while sign-in still expected the old one. The fix was
``members.service.change_member_email``, which writes both rows together, and
``PUT /members/{id}`` routes through it (``members.py:272``).

``PUT /persons/{id}`` does not. It takes an untyped ``dict``, lists ``email`` in
``allowed_fields``, and does ``setattr(person, "email", value)``
(``persons.py:50``). ``Person.email`` is an association proxy onto
``Party.email``, so that write lands on the party and ``users.email`` is never
touched. The endpoint is reachable with ``self.profile.write``, so a member can
split their own account.

The tests assert the behaviour the fix should have: the two addresses move
together, and an address another account signs in with is refused. The members
endpoint is tested beside it as the control, so the asymmetry is what fails
rather than a guess about either one.
"""

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person

import pytest


def _cookie(user):
    return {"access_token": create_access_token(user.id)}


@pytest.fixture
def org(db):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(
            id=1, name="Test Club", locale="es", timezone="Europe/Madrid",
            currency="EUR", date_format="DD/MM/YYYY",
        )
        db.add(org)
    db.flush()
    return org


@pytest.fixture
def membership_type(db):
    mt = MembershipType(
        name="Split Standard", slug="split-standard", base_price=10,
        billing_frequency="annual",
    )
    db.add(mt)
    db.flush()
    return mt


def _account(db, membership_type, email, role="member"):
    """A member with a login, which is the only shape where the split matters."""
    person = Person(first_name=email.split("@")[0], last_name="Split", email=email)
    db.add(person)
    db.flush()
    user = User(
        party_id=person.party_id, email=email,
        password_hash=hash_password("password123"), role=role, is_active=True,
    )
    db.add(user)
    db.flush()
    member = Member(
        party_id=person.party_id, membership_type_id=membership_type.id,
        member_number=f"S-{user.id:04d}", status="active",
    )
    db.add(member)
    db.flush()
    return user, member


class TestPersonsEndpointKeepsTheAddressesTogether:
    def test_a_member_editing_their_own_person_row_moves_the_login_too(
        self, client, db, org, membership_type
    ):
        """The defect, from the seat that can reach it without staff rights."""
        user, _member = _account(db, membership_type, "split-self@example.com")
        client.cookies.update(_cookie(user))

        response = client.put(
            f"/api/v1/persons/{user.party_id}",
            json={"email": "split-self-new@example.com"},
        )
        assert response.status_code == 200
        db.refresh(user)

        # The mail address moved. That part works.
        assert user.person.email == "split-self-new@example.com"
        # The login must have moved with it, or the account is split: mail goes
        # to the new address and sign-in still expects the old one.
        assert user.email == "split-self-new@example.com"

    def test_staff_editing_a_person_row_moves_the_login_too(
        self, client, db, org, membership_type
    ):
        """Same write from the staff seat, which is the documented use."""
        admin, _ = _account(db, membership_type, "split-admin@example.com", role="admin")
        target, _ = _account(db, membership_type, "split-target@example.com")
        client.cookies.update(_cookie(admin))

        response = client.put(
            f"/api/v1/persons/{target.party_id}",
            json={"email": "split-target-new@example.com"},
        )
        assert response.status_code == 200
        db.refresh(target)

        assert target.person.email == "split-target-new@example.com"
        assert target.email == "split-target-new@example.com"

    def test_an_address_another_account_signs_in_with_is_refused(
        self, client, db, org, membership_type
    ):
        """``change_member_email`` raises ``EmailTaken`` here; this path checks nothing."""
        user, _ = _account(db, membership_type, "split-a@example.com")
        other, _ = _account(db, membership_type, "split-b@example.com")
        client.cookies.update(_cookie(user))

        response = client.put(
            f"/api/v1/persons/{user.party_id}",
            json={"email": other.email},
        )
        assert response.status_code == 409


class TestMembersEndpointIsTheControl:
    """The same field through the endpoint #98 was fixed in. These should pass."""

    def test_members_put_moves_both_addresses(
        self, client, db, org, membership_type
    ):
        admin, _ = _account(db, membership_type, "ctl-admin@example.com", role="admin")
        target, member = _account(db, membership_type, "ctl-target@example.com")
        client.cookies.update(_cookie(admin))

        response = client.put(
            f"/api/v1/members/{member.id}",
            json={"email": "ctl-target-new@example.com"},
        )
        assert response.status_code == 200
        db.refresh(target)

        assert target.person.email == "ctl-target-new@example.com"
        assert target.email == "ctl-target-new@example.com"

    def test_members_put_refuses_a_taken_address(
        self, client, db, org, membership_type
    ):
        admin, _ = _account(db, membership_type, "ctl2-admin@example.com", role="admin")
        target, member = _account(db, membership_type, "ctl2-target@example.com")
        other, _ = _account(db, membership_type, "ctl2-other@example.com")
        client.cookies.update(_cookie(admin))

        response = client.put(
            f"/api/v1/members/{member.id}",
            json={"email": other.email},
        )
        assert response.status_code == 409
