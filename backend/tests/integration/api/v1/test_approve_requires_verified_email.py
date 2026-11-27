"""Approval requires an address the applicant actually proved (#643).

``approve_registration`` checked ``status == "pending"`` and nothing else, so an
administrator could approve a registration whose address was never confirmed.
Approval activates the member and allocates a member number, so a fabricated
address became a member in good standing, and sign-in is gated on verification
(``auth.py:147``) so that member could never log in.

The carve-out matters as much as the guard: a member an administrator created
directly has no ``users`` row and therefore no verification state at all. The
check keys on the account, not on the member, or it would refuse every
admin-created member in the club.

This is also what makes the two deletes in #644 and #645 safe. ``receipts`` and
``sepa_mandates`` carry no ``ondelete`` on ``party_id``, so the database refuses
to delete a party with financial history; while an unverified registration can
be approved it can hold a number and a receipt, and those deletes would fail.
"""

import pytest

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.members.models import Member, MembershipType
from app.domains.members.service import create_member
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


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
        name="Approve Standard", slug="approve-standard", base_price=0,
        billing_frequency="annual",
    )
    db.add(mt)
    db.flush()
    return mt


def _admin(db, email):
    person = Person(first_name="Approver", last_name="Admin", email=email)
    db.add(person)
    db.flush()
    user = User(
        party_id=person.party_id, email=email,
        password_hash=hash_password("password123"), role="admin",
        is_active=True, email_verified=True,
    )
    db.add(user)
    db.flush()
    return user


def _applicant_with_login(db, membership_type, email, *, verified):
    """A self-registration: person, pending member, and a login of its own."""
    person = Person(first_name=email.split("@")[0], last_name="Applicant", email=email)
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


def _login(client, user):
    client.cookies.update({"access_token": create_access_token(user.id)})


class TestApprovalRequiresAVerifiedAddress:
    def test_an_unverified_applicant_is_refused(
        self, client, db, org, membership_type
    ):
        admin = _admin(db, "appr-admin1@example.com")
        _applicant, member = _applicant_with_login(
            db, membership_type, "appr-unverified@example.com", verified=False
        )
        _login(client, admin)

        response = client.post(f"/api/v1/members/{member.id}/approve")

        assert response.status_code == 403
        db.refresh(member)
        # Refused means refused: no activation and no number burned.
        assert member.status == "pending"
        assert member.member_number is None

    def test_the_refusal_says_what_to_do(self, client, db, org, membership_type):
        """The message reaches an administrator verbatim, as the login gate's does."""
        admin = _admin(db, "appr-admin2@example.com")
        _applicant, member = _applicant_with_login(
            db, membership_type, "appr-unverified2@example.com", verified=False
        )
        _login(client, admin)

        response = client.post(f"/api/v1/members/{member.id}/approve")

        assert response.status_code == 403
        assert "confirm" in response.json()["detail"].lower()

    def test_a_verified_applicant_is_approved(
        self, client, db, org, membership_type
    ):
        """The control: the guard refuses the unproven address, not approval."""
        admin = _admin(db, "appr-admin3@example.com")
        _applicant, member = _applicant_with_login(
            db, membership_type, "appr-verified@example.com", verified=True
        )
        _login(client, admin)

        response = client.post(f"/api/v1/members/{member.id}/approve")

        assert response.status_code == 200
        db.refresh(member)
        assert member.status == "active"
        assert member.member_number is not None

    def test_a_member_with_no_login_is_approved(
        self, client, db, org, membership_type
    ):
        """The carve-out. An admin-created member has no account to verify.

        Keyed on the member rather than the account, the guard would refuse
        every member an administrator ever entered by hand.
        """
        admin = _admin(db, "appr-admin4@example.com")
        member = create_member(
            db, first_name="Walk", last_name="In",
            email="appr-walkin@example.com",
            membership_type_id=membership_type.id,
        )
        db.flush()
        assert member.user is None
        _login(client, admin)

        response = client.post(f"/api/v1/members/{member.id}/approve")

        assert response.status_code == 200
        db.refresh(member)
        assert member.status == "active"
