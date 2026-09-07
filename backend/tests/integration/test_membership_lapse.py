"""Non-payment: reverting a lapsed member to the free tier, and restoring it."""

from datetime import date, timedelta
from decimal import Decimal

from app.domains.audit.models import AuditLog
from app.domains.billing.lapse_service import (
    lapse_grace_days,
    revert_lapsed_members,
)
from app.domains.billing.models import Receipt
from app.domains.billing.membership_purchase_service import purchase_membership
from app.domains.billing.recurring_billing_service import (
    DEFAULT_MEMBERSHIP_FEE_DUE_DAYS,
    membership_fee_due_days,
    run_billing,
)
from app.domains.billing.service import mark_receipt_paid
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person

TODAY = date(2026, 6, 1)
LAPSE_ON = {"membership_lapse_enabled": True}


# --- Fixtures ---


def _org(db, features=None):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(
            id=1,
            name="Lapse Test Club",
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


def _tier(db, suffix, price, *, is_default=False, frequency="annual"):
    mtype = MembershipType(
        name=f"Lapse tier {suffix}",
        slug=f"lapse-tier-{suffix}",
        base_price=Decimal(str(price)),
        billing_frequency=frequency,
        is_active=True,
        is_default=is_default,
    )
    db.add(mtype)
    db.flush()
    return mtype


def _member(db, suffix, tier):
    person = Person(
        first_name="Lapsing",
        last_name=str(suffix),
        email=f"{suffix}@lapse-test.example",
    )
    db.add(person)
    db.flush()
    member = Member(
        person_id=person.id,
        membership_type_id=tier.id,
        member_number=f"LAPSE-{suffix}",
        status="active",
        joined_at=date(2026, 1, 1),
        is_active=True,
    )
    db.add(member)
    db.flush()
    return member


def _setup(db, suffix, *, features=LAPSE_ON, price=120):
    _org(db, features)
    free = _tier(db, f"free-{suffix}", 0, is_default=True)
    paid = _tier(db, f"paid-{suffix}", price)
    member = _member(db, suffix, paid)
    return member, free, paid


def _fee(db, member, suffix, *, due_date, status="emitted", return_date=None):
    """An ordinary recurring membership fee — no purchased plan on it."""
    receipt = Receipt(
        receipt_number=f"LAPSE-FEE-{suffix}",
        member_id=member.id,
        origin="membership",
        description="Membership fee",
        base_amount=Decimal("100.00"),
        vat_rate=Decimal("0.00"),
        vat_amount=Decimal("0.00"),
        total_amount=Decimal("100.00"),
        status=status,
        emission_date=due_date - timedelta(days=DEFAULT_MEMBERSHIP_FEE_DUE_DAYS),
        due_date=due_date,
        return_date=return_date,
        is_active=True,
    )
    db.add(receipt)
    db.flush()
    return receipt


def _long_overdue(db, member, suffix, **kwargs):
    return _fee(
        db,
        member,
        suffix,
        due_date=TODAY - timedelta(days=lapse_grace_days(db) + 1),
        **kwargs,
    )


def _audit(db, member_id):
    return (
        db.query(AuditLog)
        .filter(AuditLog.table_name == "members", AuditLog.record_id == member_id)
        .all()
    )


# --- The due window membership fees get ---


class TestMembershipFeeDueWindow:
    def test_defaults_to_a_short_window_of_its_own(self, db):
        _org(db, {})

        assert membership_fee_due_days(db) == 7

    def test_is_not_the_general_invoice_window(self, db):
        _org(db, {"recurring_billing_due_days": 30})

        assert membership_fee_due_days(db) == 7

    def test_is_configurable(self, db):
        _org(db, {"membership_fee_due_days": 5})

        assert membership_fee_due_days(db) == 5

    def test_a_scheduled_fee_is_due_within_it(self, db):
        _org(db, {"membership_fee_due_days": 5})
        _member(db, "window", _tier(db, "window", 120, frequency="monthly"))

        run = run_billing(db, "monthly", "scheduled", today=TODAY)

        assert run.receipts_generated == 1
        receipt = db.query(Receipt).filter(Receipt.origin == "membership").first()
        assert receipt.due_date == TODAY + timedelta(days=5)


# --- Reverting a lapsed member ---


class TestReversion:
    def test_reverts_a_member_past_the_grace_window(self, db):
        member, free, paid = _setup(db, "basic")
        _long_overdue(db, member, "basic")

        summary = revert_lapsed_members(db, today=TODAY)

        assert summary["lapsed"] == 1
        assert member.membership_type_id == free.id
        assert member.membership_reverted_from_id == paid.id
        assert member.membership_reverted_at is not None

    def test_leaves_a_member_still_inside_the_grace_window(self, db):
        member, _, paid = _setup(db, "inside")
        _fee(
            db,
            member,
            "inside",
            due_date=TODAY - timedelta(days=lapse_grace_days(db) - 1),
        )

        summary = revert_lapsed_members(db, today=TODAY)

        assert summary["lapsed"] == 0
        assert member.membership_type_id == paid.id

    def test_a_returned_receipt_lapses_from_its_return_date(self, db):
        member, free, _ = _setup(db, "returned")
        # Due only yesterday, but the bank bounced it long enough ago that the
        # grace counted from the return has run out.
        _fee(
            db,
            member,
            "returned",
            due_date=TODAY - timedelta(days=1),
            status="returned",
            return_date=TODAY - timedelta(days=lapse_grace_days(db) + 1),
        )

        revert_lapsed_members(db, today=TODAY)

        assert member.membership_type_id == free.id

    def test_does_not_depend_on_payment_reminders_being_enabled(self, db):
        # The fee never reached ``overdue`` because dunning is off — the state a
        # status-anchored reversion would have waited for for ever.
        member, free, _ = _setup(
            db, "nodunning", features={**LAPSE_ON, "payment_reminders_enabled": False}
        )
        _long_overdue(db, member, "nodunning", status="emitted")

        revert_lapsed_members(db, today=TODAY)

        assert member.membership_type_id == free.id

    def test_does_nothing_while_reversion_is_switched_off(self, db):
        member, _, paid = _setup(db, "off", features={})
        _long_overdue(db, member, "off")

        summary = revert_lapsed_members(db, today=TODAY)

        assert summary["lapsed"] == 0
        assert member.membership_type_id == paid.id

    def test_does_not_touch_member_status(self, db):
        member, _, _ = _setup(db, "status")
        _long_overdue(db, member, "status")

        revert_lapsed_members(db, today=TODAY)

        assert member.status == "active"
        assert member.is_active is True

    def test_leaves_the_unpaid_receipt_standing_as_debt(self, db):
        member, _, _ = _setup(db, "debt")
        receipt = _long_overdue(db, member, "debt")

        revert_lapsed_members(db, today=TODAY)

        assert receipt.status == "emitted"
        assert receipt.is_active is True
        assert receipt.total_amount == Decimal("100.00")

    def test_records_why_and_when_for_the_admin(self, db):
        member, free, paid = _setup(db, "audit")
        receipt = _long_overdue(db, member, "audit")

        revert_lapsed_members(db, today=TODAY)

        rows = _audit(db, member.id)
        assert len(rows) == 1
        assert rows[0].old_values["membership_type_id"] == paid.id
        assert rows[0].new_values["membership_type_id"] == free.id
        assert rows[0].new_values["reason"] == "membership_fee_unpaid"
        assert rows[0].new_values["receipt_number"] == receipt.receipt_number

    def test_is_idempotent(self, db):
        member, free, _ = _setup(db, "idem")
        _long_overdue(db, member, "idem")

        first = revert_lapsed_members(db, today=TODAY)
        second = revert_lapsed_members(db, today=TODAY)

        assert first["lapsed"] == 1
        assert second["lapsed"] == 0
        assert member.membership_type_id == free.id
        assert len(_audit(db, member.id)) == 1

    def test_ignores_an_unpaid_purchase_receipt(self, db):
        # An abandoned checkout granted nothing, so there is nothing to take
        # away — ``expire_unpaid_purchases`` voids it instead.
        member, free, paid = _setup(db, "purchase")
        member.membership_type_id = free.id
        db.flush()
        receipt, _ = purchase_membership(db, member, paid, today=date(2026, 1, 1))

        summary = revert_lapsed_members(db, today=TODAY)

        assert summary["lapsed"] == 0
        assert receipt.status == "emitted"

    def test_does_nothing_without_a_free_tier_to_fall_back_to(self, db):
        _org(db, LAPSE_ON)
        paid = _tier(db, "nofree", 120)
        member = _member(db, "nofree", paid)
        _long_overdue(db, member, "nofree")

        summary = revert_lapsed_members(db, today=TODAY)

        assert summary["lapsed"] == 0
        assert member.membership_type_id == paid.id


# --- Paying restores the plan ---


class TestRestoreOnPayment:
    def test_cash_restores_the_plan_the_member_lost(self, db):
        member, free, paid = _setup(db, "cash")
        receipt = _long_overdue(db, member, "cash")
        revert_lapsed_members(db, today=TODAY)
        assert member.membership_type_id == free.id

        mark_receipt_paid(db, receipt, payment_method="cash", payment_date=TODAY)

        assert member.membership_type_id == paid.id
        assert member.membership_reverted_from_id is None
        assert member.membership_reverted_at is None

    def test_restoration_is_recorded(self, db):
        member, _, paid = _setup(db, "restore-audit")
        receipt = _long_overdue(db, member, "restore-audit")
        revert_lapsed_members(db, today=TODAY)

        mark_receipt_paid(db, receipt, payment_method="bank_transfer")

        reasons = [row.new_values["reason"] for row in _audit(db, member.id)]
        assert reasons == ["membership_fee_unpaid", "membership_fee_paid"]

    def test_a_member_who_never_lapsed_is_left_alone(self, db):
        member, _, paid = _setup(db, "notlapsed")
        receipt = _fee(db, member, "notlapsed", due_date=TODAY + timedelta(days=3))

        mark_receipt_paid(db, receipt, payment_method="cash")

        assert member.membership_type_id == paid.id
        assert len(_audit(db, member.id)) == 0

    def test_a_plan_bought_since_the_lapse_wins(self, db):
        member, free, paid = _setup(db, "boughtback")
        receipt = _long_overdue(db, member, "boughtback")
        revert_lapsed_members(db, today=TODAY)
        other = _tier(db, "other-boughtback", 300)
        purchase, _ = purchase_membership(db, member, other, today=TODAY)
        mark_receipt_paid(db, purchase, payment_method="card")
        assert member.membership_type_id == other.id

        mark_receipt_paid(db, receipt, payment_method="cash")

        assert member.membership_type_id == other.id
        assert member.membership_reverted_from_id is None

    def test_a_member_can_lapse_pay_and_lapse_again(self, db):
        member, free, paid = _setup(db, "twice")
        first = _long_overdue(db, member, "twice-1")
        revert_lapsed_members(db, today=TODAY)
        mark_receipt_paid(db, first, payment_method="cash")
        assert member.membership_type_id == paid.id

        later = TODAY + timedelta(days=90)
        _fee(
            db,
            member,
            "twice-2",
            due_date=later - timedelta(days=lapse_grace_days(db) + 1),
        )
        summary = revert_lapsed_members(db, today=later)

        assert summary["lapsed"] == 1
        assert member.membership_type_id == free.id
        assert member.membership_reverted_from_id == paid.id
