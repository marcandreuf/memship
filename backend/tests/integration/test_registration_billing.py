"""Every path that confirms a registration must invoice it.

The receipt used to be created only in ``register_member``, and only when the
seat was free at that moment. A member promoted off the waitlist, or confirmed
by an admin, held a place in a paid activity and was never billed — silently,
since nothing reconciles registrations against receipts.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from itertools import count

import pytest

from app.domains.activities.models import Activity, ActivityPrice
from app.domains.activities.registration_service import (
    admin_change_status,
    cancel_registration,
    register_member,
)
from app.domains.billing.models import Receipt
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person

PRICE = Decimal("50.00")


@pytest.fixture
def org(db):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(id=1, name="Billing Club", default_vat_rate=21)
        db.add(org)
        db.flush()
    return org


@pytest.fixture
def membership_type(db):
    mt = MembershipType(name="Reg Billing", slug="reg-billing", is_active=True)
    db.add(mt)
    db.flush()
    return mt


def _member(db, membership_type, suffix):
    person = Person(
        first_name="Seat", last_name=suffix, email=f"seat-{suffix}@examplee6e3b1.com"
    )
    db.add(person)
    db.flush()
    member = Member(
        person_id=person.id,
        membership_type_id=membership_type.id,
        member_number=f"SB-{suffix}",
        status="active",
    )
    db.add(member)
    db.flush()
    return member


_slugs = count(1)


def _activity(db, *, max_participants=1, amount=PRICE, waiting_list=True):
    now = datetime.now(timezone.utc)
    activity = Activity(
        name="Paid Activity",
        slug=f"paid-activity-{next(_slugs)}",
        starts_at=now + timedelta(days=10),
        ends_at=now + timedelta(days=11),
        registration_starts_at=now - timedelta(days=1),
        registration_ends_at=now + timedelta(days=9),
        max_participants=max_participants,
        status="published",
        is_active=True,
        features={"waiting_list": waiting_list},
    )
    db.add(activity)
    db.flush()
    price = ActivityPrice(
        activity_id=activity.id,
        name="Standard",
        amount=amount,
        is_default=True,
        is_active=True,
    )
    db.add(price)
    db.flush()
    return activity, price


def _receipts_for(db, registration):
    return (
        db.query(Receipt)
        .filter(Receipt.registration_id == registration.id)
        .order_by(Receipt.id)
        .all()
    )


class TestWaitlistPromotionBills:
    def test_the_promoted_member_gets_a_receipt(self, db, org, membership_type):
        activity, price = _activity(db)
        first = _member(db, membership_type, "first")
        second = _member(db, membership_type, "second")

        confirmed = register_member(db, activity, first, price.id)
        waitlisted = register_member(db, activity, second, price.id)
        assert confirmed.status == "confirmed"
        assert waitlisted.status == "waitlist"
        assert _receipts_for(db, waitlisted) == []

        cancel_registration(db, confirmed)

        assert waitlisted.status == "confirmed"
        receipts = _receipts_for(db, waitlisted)
        assert len(receipts) == 1
        assert receipts[0].base_amount == PRICE
        assert receipts[0].member_id == second.id

    def test_the_cancelled_members_receipt_is_cancelled_not_reused(
        self, db, org, membership_type
    ):
        activity, price = _activity(db)
        first = _member(db, membership_type, "cfirst")
        second = _member(db, membership_type, "csecond")
        confirmed = register_member(db, activity, first, price.id)
        waitlisted = register_member(db, activity, second, price.id)

        cancel_registration(db, confirmed)

        assert _receipts_for(db, confirmed)[0].status == "cancelled"
        assert _receipts_for(db, waitlisted)[0].status != "cancelled"


class TestAdminConfirmationBills:
    def test_confirming_a_waitlisted_registration_bills_it(
        self, db, org, membership_type
    ):
        activity, price = _activity(db)
        first = _member(db, membership_type, "afirst")
        second = _member(db, membership_type, "asecond")
        register_member(db, activity, first, price.id)
        waitlisted = register_member(db, activity, second, price.id)

        admin_change_status(db, waitlisted, "confirmed")

        assert len(_receipts_for(db, waitlisted)) == 1

    def test_re_confirming_after_a_cancellation_bills_again(
        self, db, org, membership_type
    ):
        """The first receipt was cancelled with the registration, so the member
        owes for the seat they have just been given back."""
        activity, price = _activity(db, max_participants=5)
        member = _member(db, membership_type, "recon")
        registration = register_member(db, activity, member, price.id)
        cancel_registration(db, registration)

        admin_change_status(db, registration, "confirmed")

        receipts = _receipts_for(db, registration)
        assert [r.status for r in receipts] == ["cancelled", "emitted"]

    def test_a_status_change_that_is_not_a_confirmation_bills_nothing(
        self, db, org, membership_type
    ):
        activity, price = _activity(db, max_participants=5)
        member = _member(db, membership_type, "nocon")
        registration = register_member(db, activity, member, price.id)
        registration.status = "waitlist"
        db.flush()
        for receipt in _receipts_for(db, registration):
            receipt.status = "cancelled"
        db.flush()

        admin_change_status(db, registration, "pending")

        assert all(r.status == "cancelled" for r in _receipts_for(db, registration))


class TestBillingIsNotDuplicated:
    def test_a_registration_already_billed_is_not_billed_twice(
        self, db, org, membership_type
    ):
        activity, price = _activity(db, max_participants=5)
        member = _member(db, membership_type, "twice")
        registration = register_member(db, activity, member, price.id)
        assert len(_receipts_for(db, registration)) == 1

        registration.status = "waitlist"
        db.flush()
        admin_change_status(db, registration, "confirmed")

        assert len(_receipts_for(db, registration)) == 1

    def test_a_free_activity_is_never_billed(self, db, org, membership_type):
        activity, price = _activity(db, max_participants=5, amount=Decimal("0.00"))
        member = _member(db, membership_type, "free")
        first = _member(db, membership_type, "free2")

        registration = register_member(db, activity, member, price.id)
        promoted = register_member(db, activity, first, price.id)
        admin_change_status(db, promoted, "waitlist")
        admin_change_status(db, promoted, "confirmed")

        assert _receipts_for(db, registration) == []
        assert _receipts_for(db, promoted) == []


# --- The quote must match the invoice (#220) -------------------------------


class TestTheQuotedPriceIsWhatIsInvoiced:
    """A member was shown the stored base and invoiced the base plus VAT, so the
    figure they agreed to was not the figure they owed."""

    def test_the_price_list_carries_the_tax_inclusive_total(self, client, db, org, membership_type):
        from app.core.security.jwt import create_access_token
        from app.domains.auth.models import User
        from app.core.security.password import hash_password

        activity, price = _activity(db, amount=Decimal("95.00"))
        person = Person(first_name="Q", last_name="Quote", email="quote@examplee6e3b1.com")
        db.add(person)
        db.flush()
        user = User(
            person_id=person.id,
            email="quote@examplee6e3b1.com",
            password_hash=hash_password("password123"),
            role="admin",
            is_active=True,
        )
        db.add(user)
        db.flush()

        resp = client.get(
            f"/api/v1/activities/{activity.id}/prices/",
            cookies={"access_token": create_access_token(user.id)},
        )

        assert resp.status_code == 200
        quoted = resp.json()[0]
        assert quoted["amount"] == 95.00
        assert quoted["vat_rate"] == 21.0
        assert quoted["vat_amount"] == 19.95
        assert quoted["total_amount"] == 114.95

    def test_the_quote_equals_the_receipt_it_produces(self, db, org, membership_type):
        """The two numbers come from one rate resolution, so they cannot drift."""
        from app.domains.billing.service import activity_vat_rate, calculate_vat

        activity, price = _activity(db, amount=Decimal("95.00"))
        member = _member(db, membership_type, "quote-eq")

        rate = activity_vat_rate(db, activity.tax_rate)
        _, quoted_total = calculate_vat(Decimal(str(price.amount)), rate)

        registration = register_member(db, activity=activity, member=member, price_id=price.id)
        db.flush()

        receipt = _receipts_for(db, registration)[0]
        assert receipt.total_amount == quoted_total
        assert receipt.base_amount == Decimal("95.00")

    def test_an_activity_rate_overrides_the_org_default(self, db, org, membership_type):
        activity, price = _activity(db, amount=Decimal("100.00"))
        activity.tax_rate = Decimal("10.00")
        db.flush()

        member = _member(db, membership_type, "quote-rate")
        registration = register_member(db, activity=activity, member=member, price_id=price.id)
        db.flush()

        from app.domains.billing.service import activity_vat_rate

        assert activity_vat_rate(db, activity.tax_rate) == Decimal("10.00")
        assert _receipts_for(db, registration)[0].total_amount == Decimal("110.00")

    def test_a_zero_activity_rate_falls_back_to_the_org_default(self, db, org, membership_type):
        """`generate_activity_receipt` treated 0 as unset, and the quote has to
        agree with that rather than quote a tax-free total."""
        from app.domains.billing.service import activity_vat_rate

        activity, _ = _activity(db, amount=Decimal("100.00"))
        activity.tax_rate = Decimal("0")
        db.flush()

        assert activity_vat_rate(db, activity.tax_rate) == Decimal("21")

    def test_the_registration_reports_what_it_is_billed_at(self, db, org, membership_type):
        activity, price = _activity(db, amount=Decimal("95.00"))
        member = _member(db, membership_type, "quote-reg")
        registration = register_member(db, activity=activity, member=member, price_id=price.id)
        db.flush()

        from app.api.v1.endpoints.registrations import _vat_fields

        fields = _vat_fields(db, registration, activity)
        assert fields["total_amount"] == 114.95
        assert fields["vat_rate"] == 21.0

    def test_a_free_registration_quotes_no_total(self, db, org, membership_type):
        activity, price = _activity(db, amount=Decimal("0.00"))
        member = _member(db, membership_type, "quote-free")
        registration = register_member(db, activity=activity, member=member, price_id=price.id)
        db.flush()

        from app.api.v1.endpoints.registrations import _vat_fields

        assert _vat_fields(db, registration, activity) == {}
        assert _receipts_for(db, registration) == []
