"""Ownership and write-key guards on the self-service routes.

Three findings share one shape — a guard that trusts the wrong column or the
wrong permission key:

* receipts resolved the caller's member row through ``Person.email``, which is
  not unique, so the answer could be somebody else's member (C5);
* ``PUT /members/{id}`` checked ownership but not *which fields* a member may
  write, so a member could reassign their own membership type (C6);
* cancelling a registration keyed off ``registrations.read``, handing a
  view-only role destructive power (H13).
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.activities.models import Activity, Registration
from app.domains.auth.models import Role, RolePermission, User, UserRoleAssignment
from app.domains.billing.models import Receipt
from app.domains.members.models import Member, MembershipType
from app.domains.persons.models import Person


def _cookie(user):
    return {"access_token": create_access_token(user.id)}


@pytest.fixture
def cheap_type(db):
    mt = MembershipType(
        name="Guard Free", slug="guard-free", base_price=0, billing_frequency="annual"
    )
    db.add(mt)
    db.flush()
    return mt


@pytest.fixture
def standard_type(db):
    mt = MembershipType(
        name="Guard Standard", slug="guard-standard", base_price=120,
        billing_frequency="annual",
    )
    db.add(mt)
    db.flush()
    return mt


def _account(db, membership_type, email, *, role="member", person_email=None):
    person = Person(
        first_name=email.split("@")[0], last_name="Guard",
        email=person_email if person_email is not None else email,
    )
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id, email=email,
        password_hash=hash_password("password123"), role=role, is_active=True,
    )
    db.add(user)
    db.flush()
    member = Member(
        person_id=person.id, user_id=user.id,
        membership_type_id=membership_type.id, status="active",
    )
    db.add(member)
    db.flush()
    return user, member


def _grant(db, user, slug, keys):
    """Give ``user`` a custom role holding exactly ``keys``.

    The conftest hook already pinned ``member`` on the account, so the caller
    keeps the ``self.*`` namespace — which is what the route dependencies ask
    for. These extra keys are what the inline branch inside the route reads.
    """
    role = Role(slug=slug, name=slug, is_system=False)
    db.add(role)
    db.flush()
    for key in keys:
        db.add(RolePermission(role_id=role.id, permission_key=key))
    db.add(UserRoleAssignment(user_id=user.id, role_id=role.id))
    db.flush()
    db.expire(user)
    return role


def _receipt(db, member, number, session_id):
    receipt = Receipt(
        receipt_number=number,
        member_id=member.id,
        origin="membership",
        description="Guard receipt",
        base_amount=Decimal("100.00"),
        vat_rate=Decimal("0.00"),
        vat_amount=Decimal("0.00"),
        total_amount=Decimal("100.00"),
        status="emitted",
        emission_date=date.today(),
        stripe_checkout_session_id=session_id,
    )
    db.add(receipt)
    db.flush()
    return receipt


class TestReceiptsResolveTheMemberThroughTheUserLink:
    def test_a_shared_person_email_does_not_leak_another_members_receipt(
        self, client, db, standard_type
    ):
        """``persons.email`` is non-unique by design — a minor and their guardian
        share one — so it can never decide whose receipts these are."""
        _, victim = _account(db, standard_type, "victim-guard@examplee6e3b1.com")
        attacker_user, _ = _account(
            db, standard_type, "attacker-guard@examplee6e3b1.com",
            person_email="victim-guard@examplee6e3b1.com",
        )
        receipt = _receipt(db, victim, "FAC-GUARD-1", "cs_guard_1")

        r = client.get(
            f"/api/v1/receipts/by-stripe-session/{receipt.stripe_checkout_session_id}",
            cookies=_cookie(attacker_user),
        )

        assert r.status_code == 403

    def test_own_receipts_are_listed_when_the_person_email_differs_from_the_login(
        self, client, db, standard_type
    ):
        """An admin correcting the Person record used to break self-service
        billing outright: the lookup matched on the login email and 404'd."""
        user, member = _account(
            db, standard_type, "renamed-guard@examplee6e3b1.com",
            person_email="old-address-guard@examplee6e3b1.com",
        )
        _receipt(db, member, "FAC-GUARD-2", "cs_guard_2")

        r = client.get("/api/v1/members/me/receipts", cookies=_cookie(user))

        assert r.status_code == 200
        assert [i["receipt_number"] for i in r.json()["items"]] == ["FAC-GUARD-2"]


class TestPaymentInitiationTakesTheWriteKey:
    def test_a_view_only_billing_role_cannot_start_a_payment_for_another_member(
        self, client, db, standard_type
    ):
        viewer, _ = _account(db, standard_type, "billing-viewer@examplee6e3b1.com")
        _grant(db, viewer, "billing-viewer", {"billing.read"})
        _, other = _account(db, standard_type, "billing-other@examplee6e3b1.com")
        receipt = _receipt(db, other, "FAC-GUARD-3", "cs_guard_3")

        r = client.post(
            f"/api/v1/receipts/{receipt.id}/redsys/initiate",
            json={"method": "card"},
            cookies=_cookie(viewer),
        )

        assert r.status_code == 403

    def test_a_view_only_billing_role_still_reads_any_receipt(
        self, client, db, standard_type
    ):
        viewer, _ = _account(db, standard_type, "billing-viewer-2@examplee6e3b1.com")
        _grant(db, viewer, "billing-viewer-2", {"billing.read"})
        _, other = _account(db, standard_type, "billing-other-2@examplee6e3b1.com")
        receipt = _receipt(db, other, "FAC-GUARD-4", "cs_guard_4")

        r = client.get(
            f"/api/v1/receipts/by-stripe-session/{receipt.stripe_checkout_session_id}",
            cookies=_cookie(viewer),
        )

        assert r.status_code == 200


class TestMemberSelfEditIsFieldLimited:
    def test_a_member_cannot_reassign_their_own_membership_type(
        self, client, db, standard_type, cheap_type
    ):
        """Membership type sets the recurring fee and unlocks restricted
        activities — a self-service downgrade to a €0 tier."""
        user, member = _account(db, standard_type, "downgrade-guard@examplee6e3b1.com")

        r = client.put(
            f"/api/v1/members/{member.id}",
            json={"membership_type_id": cheap_type.id},
            cookies=_cookie(user),
        )

        assert r.status_code == 403
        db.refresh(member)
        assert member.membership_type_id == standard_type.id

    def test_a_member_cannot_write_internal_notes(
        self, client, db, standard_type
    ):
        user, member = _account(db, standard_type, "notes-guard@examplee6e3b1.com")

        r = client.put(
            f"/api/v1/members/{member.id}",
            json={"internal_notes": "approved by me"},
            cookies=_cookie(user),
        )

        assert r.status_code == 403
        db.refresh(member)
        assert member.internal_notes is None

    def test_a_member_cannot_rewrite_their_person_email(
        self, client, db, standard_type
    ):
        """Which is what made the shared-email receipt lookup exploitable, and
        what desynchronises the Person row from ``users.email``."""
        user, member = _account(db, standard_type, "email-guard@examplee6e3b1.com")

        r = client.put(
            f"/api/v1/members/{member.id}",
            json={"email": "someone-else-guard@examplee6e3b1.com"},
            cookies=_cookie(user),
        )

        assert r.status_code == 403
        db.refresh(member)
        assert member.person.email == "email-guard@examplee6e3b1.com"

    def test_a_member_may_still_edit_their_own_name(
        self, client, db, standard_type
    ):
        user, member = _account(db, standard_type, "rename-guard@examplee6e3b1.com")

        r = client.put(
            f"/api/v1/members/{member.id}",
            json={"first_name": "Renamed"},
            cookies=_cookie(user),
        )

        assert r.status_code == 200
        db.refresh(member)
        assert member.person.first_name == "Renamed"

    def test_staff_may_still_set_every_field(
        self, client, db, standard_type, cheap_type
    ):
        staff, _ = _account(db, standard_type, "staff-guard@examplee6e3b1.com", role="admin")
        _, member = _account(db, standard_type, "target-guard@examplee6e3b1.com")

        r = client.put(
            f"/api/v1/members/{member.id}",
            json={"membership_type_id": cheap_type.id, "internal_notes": "moved tier"},
            cookies=_cookie(staff),
        )

        assert r.status_code == 200
        db.refresh(member)
        assert member.membership_type_id == cheap_type.id
        assert member.internal_notes == "moved tier"


@pytest.fixture
def activity(db):
    now = datetime.now(timezone.utc)
    activity = Activity(
        name="Guard Camp",
        slug="guard-camp",
        status="published",
        starts_at=now + timedelta(days=10),
        ends_at=now + timedelta(days=11),
        registration_starts_at=now - timedelta(days=1),
        registration_ends_at=now + timedelta(days=9),
        max_participants=50,
        current_participants=1,
    )
    db.add(activity)
    db.flush()
    return activity


class TestCancellationTakesTheWriteKey:
    def test_a_view_only_registrations_role_cannot_cancel_another_members_place(
        self, client, db, standard_type, activity
    ):
        viewer, _ = _account(db, standard_type, "reg-viewer@examplee6e3b1.com")
        _grant(db, viewer, "registrations-viewer", {"registrations.read"})
        _, other = _account(db, standard_type, "reg-other@examplee6e3b1.com")
        registration = Registration(
            activity_id=activity.id, member_id=other.id, status="confirmed"
        )
        db.add(registration)
        db.flush()

        r = client.delete(
            f"/api/v1/registrations/{registration.id}", cookies=_cookie(viewer)
        )

        assert r.status_code == 403
        db.refresh(registration)
        assert registration.status == "confirmed"

    def test_the_write_key_still_cancels_any_registration(
        self, client, db, standard_type, activity
    ):
        editor, _ = _account(db, standard_type, "reg-editor@examplee6e3b1.com")
        _grant(db, editor, "registrations-editor", {"registrations.write"})
        _, other = _account(db, standard_type, "reg-other-2@examplee6e3b1.com")
        registration = Registration(
            activity_id=activity.id, member_id=other.id, status="confirmed"
        )
        db.add(registration)
        db.flush()

        r = client.delete(
            f"/api/v1/registrations/{registration.id}", cookies=_cookie(editor)
        )

        assert r.status_code == 204
        db.refresh(registration)
        assert registration.status == "cancelled"