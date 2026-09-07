"""Buying a membership plan: the receipt it raises, and the plan payment grants."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.domains.billing.membership_purchase_service import (
    expire_unpaid_purchases,
    purchase_membership,
    quote_membership_purchase,
)
from app.domains.billing.models import Receipt, Remittance
from app.domains.billing.recurring_billing_service import run_billing
from app.domains.billing.service import mark_receipt_paid, mark_receipts_paid
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


# --- Fixtures ---


def _org(db, features=None):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(
            id=1,
            name="Buy Test Club",
            currency="EUR",
            invoice_prefix="FAC",
            invoice_annual_reset=True,
            default_vat_rate=Decimal("21.00"),
        )
        db.add(org)
    if features is not None:
        org.features = features
    db.flush()
    return org


def _tier(db, suffix, price, frequency="annual", is_active=True, is_default=False):
    mtype = MembershipType(
        name=f"Tier {suffix}",
        slug=f"tier-{suffix}",
        base_price=Decimal(str(price)),
        billing_frequency=frequency,
        is_active=is_active,
        is_default=is_default,
    )
    db.add(mtype)
    db.flush()
    return mtype


def _member(db, suffix, tier, status="active"):
    person = Person(
        first_name="Buyer",
        last_name=f"{suffix}",
        email=f"{suffix}@buy-test.example",
    )
    db.add(person)
    db.flush()
    member = Member(
        person_id=person.id,
        membership_type_id=tier.id,
        member_number=f"BUY-{suffix}",
        status=status,
        joined_at=date(2026, 1, 1),
        is_active=True,
    )
    db.add(member)
    db.flush()
    return member


def _setup(db, suffix, *, price=200, frequency="annual", features=None):
    _org(db, features)
    free = _tier(db, f"free-{suffix}", 0, "annual")
    paid = _tier(db, f"paid-{suffix}", price, frequency)
    member = _member(db, suffix, free)
    return member, free, paid


def _remittance(db, number, total):
    remittance = Remittance(
        remittance_number=number,
        remittance_type="sepa",
        status="submitted",
        emission_date=date(2026, 3, 15),
        due_date=date(2026, 3, 20),
        total_amount=total,
        receipt_count=1,
        creditor_name="Buy Test Club",
        creditor_iban="ES9121000418450200051332",
        creditor_id="ES12ZZZ00000000A",
    )
    db.add(remittance)
    db.flush()
    return remittance


def _membership_receipts(db, member_id):
    return (
        db.query(Receipt)
        .filter(
            Receipt.member_id == member_id,
            Receipt.origin == "membership",
            Receipt.is_active.is_(True),
            Receipt.status != "cancelled",
        )
        .all()
    )


# --- The receipt a purchase raises ---


class TestPurchaseReceipt:
    def test_prorated_and_stamped_with_the_calendar_period(self, db):
        member, _, paid = _setup(db, "prorate", price=200, frequency="annual")

        receipt, quote = purchase_membership(db, member, paid, today=date(2026, 3, 15))

        # March to December: 10 of 12 months of 200.00.
        assert quote.months_charged == 10
        assert quote.months_in_period == 12
        assert receipt.base_amount == Decimal("166.67")
        assert receipt.billing_period_start == date(2026, 1, 1)
        assert receipt.billing_period_end == date(2026, 12, 31)
        assert receipt.purchased_membership_type_id == paid.id
        assert receipt.origin == "membership"
        assert receipt.description == "Tier paid-prorate — 10/12"

    def test_receipt_is_emitted_so_the_existing_checkouts_accept_it(self, db):
        member, _, paid = _setup(db, "emitted")

        receipt, _ = purchase_membership(db, member, paid, today=date(2026, 3, 15))

        # `stripe/checkout` and `redsys/initiate` both refuse anything that is
        # not emitted or overdue.
        assert receipt.status == "emitted"
        assert receipt.is_batchable is True

    def test_due_date_follows_the_configured_window(self, db):
        member, _, paid = _setup(
            db, "due", features={"recurring_billing_due_days": 7}
        )

        receipt, _ = purchase_membership(db, member, paid, today=date(2026, 3, 15))

        assert receipt.due_date == date(2026, 3, 22)

    def test_total_carries_the_vat_the_member_actually_pays(self, db):
        member, _, paid = _setup(db, "vat", price=200, frequency="annual")

        receipt, quote = purchase_membership(db, member, paid, today=date(2026, 3, 15))

        assert quote.base_amount == Decimal("166.67")
        assert quote.vat_rate == Decimal("21.00")
        assert quote.vat_amount == Decimal("35.00")
        assert quote.total_amount == Decimal("201.67")
        assert receipt.total_amount == Decimal("201.67")

    def test_one_time_plan_is_charged_in_full_with_no_period(self, db):
        member, _, paid = _setup(db, "onetime", price=50, frequency="one_time")

        receipt, quote = purchase_membership(db, member, paid, today=date(2026, 3, 15))

        assert receipt.base_amount == Decimal("50.00")
        assert receipt.billing_period_start is None
        assert receipt.billing_period_end is None
        assert quote.is_prorated is False
        assert receipt.description == "Tier paid-onetime"

    def test_buying_does_not_move_the_member(self, db):
        member, free, paid = _setup(db, "notyet")

        purchase_membership(db, member, paid, today=date(2026, 3, 15))

        assert member.membership_type_id == free.id


# --- What a purchase refuses ---


class TestPurchaseRefusals:
    def test_inactive_plan(self, db):
        _org(db)
        free = _tier(db, "free-inactive", 0)
        member = _member(db, "inactive", free)
        retired = _tier(db, "retired", 100, is_active=False)

        with pytest.raises(HTTPException) as exc:
            purchase_membership(db, member, retired)
        assert exc.value.status_code == 400

    def test_the_plan_already_held(self, db):
        _org(db)
        paid = _tier(db, "held", 100)
        member = _member(db, "held", paid)

        with pytest.raises(HTTPException) as exc:
            purchase_membership(db, member, paid)
        assert exc.value.status_code == 400

    def test_a_free_plan_is_granted_not_sold(self, db):
        member, free, _ = _setup(db, "freeplan")
        other_free = _tier(db, "free-other", 0)

        with pytest.raises(HTTPException) as exc:
            purchase_membership(db, member, other_free)
        assert exc.value.status_code == 400

    def test_a_sign_up_still_awaiting_approval(self, db):
        _org(db)
        free = _tier(db, "free-pending", 0)
        member = _member(db, "pending", free, status="pending")
        paid = _tier(db, "paid-pending", 100)

        with pytest.raises(HTTPException) as exc:
            purchase_membership(db, member, paid)
        assert exc.value.status_code == 403

    def test_a_quote_refuses_what_a_purchase_refuses(self, db):
        _org(db)
        free = _tier(db, "free-quote", 0)
        member = _member(db, "quote", free)
        retired = _tier(db, "quote-retired", 100, is_active=False)

        with pytest.raises(HTTPException):
            quote_membership_purchase(db, member, retired)

    def test_a_quote_raises_nothing(self, db):
        member, _, paid = _setup(db, "quoteonly")

        quote = quote_membership_purchase(db, member, paid, today=date(2026, 3, 15))

        assert quote.total_amount == Decimal("201.67")
        assert _membership_receipts(db, member.id) == []


# --- Changing your mind ---


class TestSupersedingAPurchase:
    def test_a_new_purchase_voids_the_pending_one(self, db):
        member, _, first_plan = _setup(db, "changemind")
        second_plan = _tier(db, "changemind-2", 300)

        first, _ = purchase_membership(db, member, first_plan, today=date(2026, 3, 15))
        second, _ = purchase_membership(db, member, second_plan, today=date(2026, 3, 16))

        db.refresh(first)
        assert first.status == "cancelled"
        assert second.status == "emitted"
        assert [r.id for r in _membership_receipts(db, member.id)] == [second.id]

    def test_a_purchase_already_handed_to_the_bank_is_left_alone(self, db):
        member, _, first_plan = _setup(db, "inremittance")
        second_plan = _tier(db, "inremittance-2", 300)

        first, _ = purchase_membership(db, member, first_plan, today=date(2026, 3, 15))
        remittance = _remittance(db, "REM-BUY-1", first.total_amount)
        first.remittance_id = remittance.id
        db.flush()

        purchase_membership(db, member, second_plan, today=date(2026, 3, 16))

        db.refresh(first)
        assert first.status == "emitted"


# --- Expiry ---


class TestExpiry:
    def test_an_unpaid_purchase_is_voided_past_its_due_date(self, db):
        member, _, paid = _setup(
            db, "expire", features={"recurring_billing_due_days": 7}
        )
        receipt, _ = purchase_membership(db, member, paid, today=date(2026, 3, 15))

        assert expire_unpaid_purchases(db, date(2026, 3, 23)) == 1
        db.refresh(receipt)
        assert receipt.status == "cancelled"

    def test_it_survives_up_to_and_including_the_due_date(self, db):
        member, _, paid = _setup(
            db, "notyetdue", features={"recurring_billing_due_days": 7}
        )
        receipt, _ = purchase_membership(db, member, paid, today=date(2026, 3, 15))

        assert expire_unpaid_purchases(db, date(2026, 3, 22)) == 0
        db.refresh(receipt)
        assert receipt.status == "emitted"

    def test_a_paid_purchase_is_never_touched(self, db):
        member, _, paid = _setup(
            db, "paidnotexpired", features={"recurring_billing_due_days": 7}
        )
        receipt, _ = purchase_membership(db, member, paid, today=date(2026, 3, 15))
        mark_receipt_paid(db, receipt, payment_method="cash")

        assert expire_unpaid_purchases(db, date(2026, 4, 30)) == 0
        db.refresh(receipt)
        assert receipt.status == "paid"

    def test_an_ordinary_membership_fee_is_never_expired(self, db):
        member, _, paid = _setup(db, "ordinaryfee")
        member.membership_type_id = paid.id
        db.flush()
        run = run_billing(db, "annual", "scheduled", today=date(2026, 1, 1))
        assert run.receipts_generated == 1

        assert expire_unpaid_purchases(db, date(2027, 1, 1)) == 0
        fee = _membership_receipts(db, member.id)[0]
        assert fee.status == "emitted"

    def test_expiry_runs_before_the_dunning_pass(self, db):
        member, _, paid = _setup(
            db,
            "beforedunning",
            features={
                "recurring_billing_due_days": 7,
                "payment_reminders_enabled": True,
            },
        )
        receipt, _ = purchase_membership(db, member, paid, today=date(2026, 3, 15))

        from app.domains.billing.reminder_service import run_scheduled_reminders

        expire_unpaid_purchases(db, date(2026, 3, 23))
        summary = run_scheduled_reminders(db, date(2026, 3, 23))

        db.refresh(receipt)
        assert receipt.status == "cancelled"
        assert summary["overdue_marked"] == 0
        assert summary["reminders_sent"] == 0


# --- Activation ---


class TestActivation:
    def test_paying_grants_the_plan(self, db):
        member, free, paid = _setup(db, "activate")
        receipt, _ = purchase_membership(db, member, paid, today=date(2026, 3, 15))
        assert member.membership_type_id == free.id

        mark_receipt_paid(db, receipt, payment_method="cash")

        assert member.membership_type_id == paid.id

    @pytest.mark.parametrize(
        "payment_method",
        ["cash", "bank_transfer", "stripe_checkout", "redsys", "direct_debit"],
    )
    def test_every_payment_method_grants_it_identically(self, db, payment_method):
        member, _, paid = _setup(db, f"method-{payment_method.replace('_', '-')}")
        receipt, _ = purchase_membership(db, member, paid, today=date(2026, 3, 15))

        mark_receipt_paid(db, receipt, payment_method=payment_method)

        assert member.membership_type_id == paid.id

    def test_a_sepa_remittance_grants_it_on_reconciliation(self, db):
        member, free, paid = _setup(db, "sepa")
        receipt, _ = purchase_membership(db, member, paid, today=date(2026, 3, 15))
        remittance = _remittance(db, "REM-BUY-SEPA", receipt.total_amount)
        receipt.remittance_id = remittance.id
        db.flush()
        assert member.membership_type_id == free.id

        # What `close_remittance` does days later, in one batch.
        mark_receipts_paid(
            db, [receipt], payment_method="direct_debit", payment_date=date(2026, 3, 25)
        )

        assert member.membership_type_id == paid.id
        assert receipt.payment_date == date(2026, 3, 25)

    def test_an_ordinary_receipt_changes_no_tier(self, db):
        member, free, paid = _setup(db, "notapurchase")
        member.membership_type_id = paid.id
        db.flush()
        run_billing(db, "annual", "scheduled", today=date(2026, 1, 1))
        fee = _membership_receipts(db, member.id)[0]
        member.membership_type_id = free.id
        db.flush()

        mark_receipt_paid(db, fee, payment_method="cash")

        assert member.membership_type_id == free.id

    def test_a_deleted_plan_leaves_the_payment_intact(self, db):
        member, free, paid = _setup(db, "deletedplan")
        receipt, _ = purchase_membership(db, member, paid, today=date(2026, 3, 15))
        # What `ON DELETE SET NULL` leaves behind.
        receipt.purchased_membership_type_id = None
        db.flush()

        mark_receipt_paid(db, receipt, payment_method="cash")

        assert receipt.status == "paid"
        assert member.membership_type_id == free.id


# --- The reason the period stamp matters ---


class TestNoDoubleBilling:
    def test_the_next_scheduled_run_skips_the_buyer(self, db):
        """A buyer who paid mid-period is not billed again for that same period.

        This is the whole point of stamping the purchase receipt with the
        calendar period: `generate_membership_fees` skips a member who already
        holds a live `membership` receipt for it. Stamped wrongly, the annual run
        would charge this member a second time for a year they have paid for.
        """
        member, _, paid = _setup(db, "nodouble", price=200, frequency="annual")

        receipt, _ = purchase_membership(db, member, paid, today=date(2026, 3, 15))
        mark_receipt_paid(db, receipt, payment_method="cash")
        assert member.membership_type_id == paid.id

        run = run_billing(db, "annual", "scheduled", today=date(2026, 3, 20))

        assert run.status == "success"
        assert run.receipts_generated == 0
        assert [r.id for r in _membership_receipts(db, member.id)] == [receipt.id]

    def test_the_run_after_the_period_ends_does_bill_them(self, db):
        """The buyer joins the ordinary cycle at the next calendar boundary."""
        member, _, paid = _setup(db, "nextperiod", price=200, frequency="annual")

        receipt, _ = purchase_membership(db, member, paid, today=date(2026, 3, 15))
        mark_receipt_paid(db, receipt, payment_method="cash")

        run = run_billing(db, "annual", "scheduled", today=date(2027, 1, 1))

        assert run.receipts_generated == 1
        fees = _membership_receipts(db, member.id)
        assert len(fees) == 2
        renewal = next(r for r in fees if r.id != receipt.id)
        assert renewal.base_amount == Decimal("200.00")
        assert renewal.billing_period_start == date(2027, 1, 1)

    def test_an_unpaid_purchase_still_stops_the_run(self, db):
        """The dedup key is the period, not the payment.

        An unpaid purchase leaves the member on the free tier, which the fee
        generator skips anyway (it only bills tiers with a price) — but if an
        admin moves them by hand while the purchase is open, the stamp is what
        stops the run raising a second receipt for months already invoiced.
        """
        member, _, paid = _setup(db, "unpaiddedup", price=200, frequency="annual")
        receipt, _ = purchase_membership(db, member, paid, today=date(2026, 3, 15))
        member.membership_type_id = paid.id
        db.flush()

        run = run_billing(db, "annual", "scheduled", today=date(2026, 3, 20))

        assert run.receipts_generated == 0
        assert [r.id for r in _membership_receipts(db, member.id)] == [receipt.id]

    def test_a_monthly_purchase_covers_the_month_it_was_bought_in(self, db):
        member, _, paid = _setup(db, "monthly", price=30, frequency="monthly")

        receipt, quote = purchase_membership(db, member, paid, today=date(2026, 3, 15))
        mark_receipt_paid(db, receipt, payment_method="cash")

        assert quote.is_prorated is False
        assert receipt.base_amount == Decimal("30.00")
        assert receipt.billing_period_start == date(2026, 3, 1)

        march = run_billing(db, "monthly", "scheduled", today=date(2026, 3, 20))
        april = run_billing(db, "monthly", "scheduled", today=date(2026, 4, 1))
        assert march.receipts_generated == 0
        assert april.receipts_generated == 1


# --- The window an abandoned purchase leaves open ---


def test_an_expired_purchase_frees_the_period_again(db):
    """Voiding does not lock the member out of buying the same period later."""
    member, _, paid = _setup(db, "rebuy", features={"recurring_billing_due_days": 7})
    first, _ = purchase_membership(db, member, paid, today=date(2026, 3, 15))
    expire_unpaid_purchases(db, date(2026, 3, 23))

    second, _ = purchase_membership(db, member, paid, today=date(2026, 4, 1))

    assert second.billing_period_start == date(2026, 1, 1)
    assert second.base_amount == Decimal("150.00")  # April to December, 9/12
    assert second.due_date == date(2026, 4, 1) + timedelta(days=7)
