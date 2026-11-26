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
touched.

There is a second half, and the two interact. ``MemberSelfUpdate`` excludes
``email`` deliberately, because it is the address the account signs in with, so
``PUT /members/{id}`` answers 403 to a self-service caller editing their own
record. This endpoint accepted it, which made it a way around that rule. While
the write landed only on the party row the login was protected by accident;
keeping the two rows together without also adopting the restriction would have
handed a member their own login address, which is worse than the split it fixes.

So the tests cover both: the field is staff-only, and when staff do write it the
two addresses move together and a taken address is refused. The members endpoint
is tested beside it as the control, so what fails is the disagreement between the
two endpoints rather than a guess about either one.
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
    def test_a_member_may_not_change_the_address_on_their_own_record(
        self, client, db, org, membership_type
    ):
        """``MemberSelfUpdate`` excludes ``email`` on purpose: it is the address
        the account signs in with, and ``PUT /members/{id}`` answers 403 for a
        self-service caller. This endpoint has to answer the same, or it is a way
        around that rule.
        """
        user, _member = _account(db, membership_type, "split-self@example.com")
        client.cookies.update(_cookie(user))

        response = client.put(
            f"/api/v1/persons/{user.party_id}",
            json={"email": "split-self-new@example.com"},
        )
        assert response.status_code == 403
        db.refresh(user)

        # Neither row moved. While the write landed only on the party row the
        # login was protected by accident; both have to be checked now.
        assert user.person.email == "split-self@example.com"
        assert user.email == "split-self@example.com"

    def test_a_member_may_still_edit_the_rest_of_their_own_record(
        self, client, db, org, membership_type
    ):
        """The refusal above is about ``email`` only, not the endpoint."""
        user, _member = _account(db, membership_type, "split-self-ok@example.com")
        client.cookies.update(_cookie(user))

        response = client.put(
            f"/api/v1/persons/{user.party_id}",
            json={"first_name": "Renamed"},
        )
        assert response.status_code == 200
        db.refresh(user)
        assert user.person.first_name == "Renamed"

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
        """``change_person_email`` raises ``EmailTaken``; this path checked nothing.

        Driven from the staff seat, since that is the only one that may write the
        field at all.
        """
        admin, _ = _account(db, membership_type, "split-a-admin@example.com", role="admin")
        target, _ = _account(db, membership_type, "split-a@example.com")
        other, _ = _account(db, membership_type, "split-b@example.com")
        client.cookies.update(_cookie(admin))

        response = client.put(
            f"/api/v1/persons/{target.party_id}",
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
