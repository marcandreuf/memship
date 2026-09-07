"""Buying a membership plan — quoting it, billing it, and granting it once paid.

A member cannot write their own ``membership_type_id``: ``MemberSelfUpdate``
excludes it because the tier sets the recurring fee and unlocks restricted
activities. Buying a plan is therefore not a relaxed profile update but its own
flow, and it splits in two.

**Buying raises a receipt and changes nothing else.** The member keeps the tier
they already hold — the free default, in the ordinary case — and every access
that tier gives, until the money actually arrives. Buying is not having.

**Paying is what grants the plan**, through ``mark_receipt_paid``: the single
place a receipt becomes paid, shared by an admin recording cash, both card
webhooks and the reconciliation of a SEPA remittance. Hanging activation there
is what makes a member who pays their treasurer in cash get their plan on
exactly the same terms as one who pays by card.

The first charge is prorated against the calendar period the purchase falls in
(see ``proration``) and the receipt is stamped with that period, because
``generate_membership_fees`` skips a member who already holds a receipt for it.
Stamped correctly the next scheduled run leaves the buyer alone; stamped wrongly
it bills them a second time for months they have already paid for.

An unpaid purchase does not become a debt. It is voided at its due date, and
starting another purchase voids whichever one is still open, so a member who
picked the wrong plan or closed the checkout tab is neither chased by the
dunning pipeline nor stuck waiting for an admin to unpick it.
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.domains.billing.models import Concept, Receipt
from app.domains.billing.proration import prorate_membership_price
from app.domains.billing.recurring_billing_service import membership_fee_due_days
from app.domains.billing.service import (
    calculate_vat,
    cancel_receipt,
    generate_receipt_number,
    membership_concept,
)
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings

logger = logging.getLogger(__name__)

# The statuses in which a purchase receipt still owes money and has therefore
# granted nothing. ``paid`` is settled, ``cancelled`` is already gone, and
# ``returned`` reaches here too: a paid receipt is terminal, so a returned one
# was never paid and never activated anything.
OPEN_PURCHASE_STATUSES = ("new", "pending", "emitted", "overdue", "returned")


@dataclass(frozen=True)
class MembershipQuote:
    """What a plan costs this member today — including the tax on it.

    ``base_amount`` is the prorated price before tax and ``total_amount`` is what
    the member actually pays. Both are here on purpose: the stored plan price is
    a base amount and VAT is only added when the receipt is raised, so anything
    quoting the plan price alone shows a figure the receipt then contradicts.
    The arithmetic is done once, here, rather than guessed at by the caller.
    """

    membership_type: MembershipType
    base_amount: Decimal
    vat_rate: Decimal
    vat_amount: Decimal
    total_amount: Decimal
    period_start: date | None
    period_end: date | None
    months_charged: int | None
    months_in_period: int | None

    @property
    def is_prorated(self) -> bool:
        """Whether this charge covers less than a whole period."""
        return (
            self.months_charged is not None
            and self.months_in_period is not None
            and self.months_charged < self.months_in_period
        )


def _assert_purchasable(member: Member, mtype: MembershipType) -> None:
    """Reject the purchases that should never reach a receipt.

    Approval is checked here as well as on the router: the router's
    ``require_approved_member`` is what a request meets first, but the service
    is also reachable from a script or a future admin-assisted flow, and "the
    sign-up is not approved yet" must not depend on which door was used.
    """
    if member.status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A membership plan cannot be bought until the sign-up is approved",
        )
    if not mtype.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This membership plan is not available",
        )
    if mtype.base_price is None or Decimal(str(mtype.base_price)) <= 0:
        # A free tier is granted, not sold. Selling one would raise a zero
        # receipt that can never be paid, so the plan would never activate.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This membership plan is free and cannot be bought",
        )
    if member.membership_type_id == mtype.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This is already the current membership plan",
        )


def _quote(
    db: Session, mtype: MembershipType, vat_rate: Decimal, today: date
) -> MembershipQuote:
    try:
        charge = prorate_membership_price(mtype.base_price, mtype.billing_frequency, today)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    vat_amount, total_amount = calculate_vat(charge.amount, vat_rate)
    return MembershipQuote(
        membership_type=mtype,
        base_amount=charge.amount,
        vat_rate=vat_rate,
        vat_amount=vat_amount,
        total_amount=total_amount,
        period_start=charge.period_start,
        period_end=charge.period_end,
        months_charged=charge.months_charged,
        months_in_period=charge.months_in_period,
    )


def _default_vat_rate(db: Session) -> Decimal:
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    return Decimal(str((org.default_vat_rate if org else None) or 21))


def quote_membership_purchase(
    db: Session, member: Member, mtype: MembershipType, today: date | None = None
) -> MembershipQuote:
    """Price ``mtype`` for ``member`` without raising anything.

    Reads the concept's VAT rate where one already exists and falls back to the
    organization default, which is the rate a concept created by the purchase
    would be given — so the quote and the receipt that follows it agree.
    """
    today = today or date.today()
    _assert_purchasable(member, mtype)

    concept = (
        db.query(Concept)
        .filter(
            Concept.code == f"membership-{mtype.slug}",
            Concept.is_active.is_(True),
        )
        .first()
    )
    vat_rate = (
        Decimal(str(concept.vat_rate)) if concept is not None else _default_vat_rate(db)
    )
    return _quote(db, mtype, vat_rate, today)


def void_open_purchases(db: Session, member_id: int) -> list[Receipt]:
    """Cancel every purchase receipt this member still owes money on.

    Called when a new purchase starts. A member who picked the wrong plan can
    then change their mind on their own; without this they would hold two live
    invoices for two plans and need an admin to take one away.

    Receipts already handed to the bank are left alone — see
    ``expire_unpaid_purchases``.
    """
    db.flush()
    open_purchases = (
        db.query(Receipt)
        .filter(
            Receipt.member_id == member_id,
            Receipt.purchased_membership_type_id.isnot(None),
            Receipt.is_active.is_(True),
            Receipt.remittance_id.is_(None),
            Receipt.status.in_(OPEN_PURCHASE_STATUSES),
        )
        .all()
    )
    for receipt in open_purchases:
        cancel_receipt(db, receipt)
    return open_purchases


def purchase_membership(
    db: Session,
    member: Member,
    mtype: MembershipType,
    today: date | None = None,
    created_by_id: int | None = None,
) -> tuple[Receipt, MembershipQuote]:
    """Raise the receipt for ``member`` buying ``mtype``, and change nothing else.

    The member stays on the tier they hold. The receipt is born ``emitted``,
    which is what the Stripe and Redsys checkout endpoints require and what
    makes it collectable in a SEPA remittance; the plan is granted only when it
    is paid.

    Does not commit — the caller owns the transaction.
    """
    today = today or date.today()
    _assert_purchasable(member, mtype)

    void_open_purchases(db, member.id)

    concept = membership_concept(db, mtype, _default_vat_rate(db))
    quote = _quote(db, mtype, Decimal(str(concept.vat_rate)), today)

    # "10 of 12 months" is an invoice line a treasurer can check by hand, so it
    # is on the receipt rather than only implied by an amount that does not match
    # the plan's advertised price.
    description = mtype.name
    if quote.is_prorated:
        description = f"{mtype.name} — {quote.months_charged}/{quote.months_in_period}"

    receipt = Receipt(
        receipt_number=generate_receipt_number(db, today),
        member_id=member.id,
        concept_id=concept.id,
        purchased_membership_type_id=mtype.id,
        # ``membership``, not a new origin: it is what the fee generator's
        # skip-if-exists check filters on, and a purchase covering the period
        # only stops the next run duplicating it if the two agree.
        origin="membership",
        description=description,
        base_amount=quote.base_amount,
        vat_rate=quote.vat_rate,
        vat_amount=quote.vat_amount,
        total_amount=quote.total_amount,
        status="emitted",
        emission_date=today,
        due_date=today + timedelta(days=membership_fee_due_days(db)),
        billing_period_start=quote.period_start,
        billing_period_end=quote.period_end,
        is_batchable=True,
        created_by=created_by_id,
    )
    db.add(receipt)
    db.flush()
    return receipt, quote


def activate_purchased_membership(db: Session, receipt: Receipt) -> bool:
    """Move the member onto the plan their receipt was raised for.

    Called inline by ``mark_receipt_paid``, inside the transaction that records
    the payment: the tier is a database effect, and a member whose payment
    committed while their plan did not would hold a paid invoice for something
    they never received.

    Returns whether a tier was actually changed. A receipt with no plan on it —
    every ordinary fee, activity and booking receipt — is not a purchase and is
    left alone, and neither is one whose plan row has since been deleted, which
    the ``ON DELETE SET NULL`` foreign key turns into exactly that case.
    """
    if receipt.purchased_membership_type_id is None:
        return False

    mtype = (
        db.query(MembershipType)
        .filter(MembershipType.id == receipt.purchased_membership_type_id)
        .first()
    )
    member = db.query(Member).filter(Member.id == receipt.member_id).first()
    if mtype is None or member is None:
        logger.error(
            "Paid purchase receipt %s has no plan or member to activate", receipt.id
        )
        return False

    if member.membership_type_id == mtype.id:
        return False

    # Deliberately not gated on ``mtype.is_active``. A club retiring a plan
    # between purchase and payment does not undo the payment, and the member
    # bought what they bought.
    member.membership_type_id = mtype.id
    # A member who lapsed and then bought their way back has chosen this plan
    # over the one they lost, so the parked tier is dropped rather than left to
    # overwrite their purchase the next time an old fee is settled.
    member.membership_reverted_from_id = None
    member.membership_reverted_at = None
    db.flush()
    return True


def expire_unpaid_purchases(db: Session, today: date | None = None) -> int:
    """Void purchase receipts nobody paid by their due date.

    An abandoned checkout is not a debt. Left open, the receipt would be marked
    overdue and then chased by the dunning pipeline for a plan the member never
    received — the wrong message, sent about money that is not owed.

    Runs before ``mark_overdue`` on the same schedule, and on the same
    ``due_date < today`` boundary, so an expiring purchase is voided rather than
    ever reaching ``overdue``.

    A receipt already in a remittance is left alone: it has been handed to the
    bank and its collection is out of our hands, so voiding it here would only
    make our records disagree with the money that is still on its way.

    Returns how many were voided. Does not commit.
    """
    today = today or date.today()
    expired = (
        db.query(Receipt)
        .filter(
            Receipt.purchased_membership_type_id.isnot(None),
            Receipt.is_active.is_(True),
            Receipt.remittance_id.is_(None),
            Receipt.status.in_(OPEN_PURCHASE_STATUSES),
            Receipt.payment_date.is_(None),
            Receipt.due_date.isnot(None),
            Receipt.due_date < today,
        )
        .all()
    )
    for receipt in expired:
        cancel_receipt(db, receipt)
    return len(expired)
