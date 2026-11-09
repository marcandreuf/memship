"""A member giving the organisation money beyond their fee.

The member can already *pay* a receipt with a card; this is the other
direction, and it reuses everything the first one needs. There is no second
gateway account, no anonymous endpoint and no new payment path: the donor is a
signed-in member, the receipt is an ordinary receipt, and the provider the club
already registered to collect fees takes the money (#434).

**The receipt is raised before the member reaches the gateway**, born
``emitted``, because that is what the Stripe and Redsys checkout endpoints
take. ``purchase_membership`` has the identical shape for the identical reason.
What follows from it is the only hard part of this module: every change of mind
leaves an unpaid receipt behind, and an abandoned donation is not a debt.

``expire_unpaid_donations`` is how that is answered, and it copies
``expire_unpaid_purchases`` rather than inventing: void on the due date, before
``mark_overdue`` can touch it, whether or not the club runs dunning at all, and
never a receipt already handed to the bank. Two guards sit on "never chase a
member for a donation they did not make" — this sweep and ``NON_DEBT_ORIGINS``
— and that is the right number, because the sweep requires a due date and a
receipt's status is also settable directly through the receipt endpoints.

A donation is **card and Bizum only**. A SEPA mandate was signed for recurring
fees, a bank return on a donation is messier than on a fee, and a direct-debit
donation would enter a remittance, which is precisely the state the sweep has
to leave alone. ``is_batchable=False`` is what enforces that, rather than a
rule written down somewhere.
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.clock import org_today
from app.domains.billing.models import Receipt
from app.domains.billing.rules import billing_int_rule
from app.domains.billing.service import cancel_receipt, generate_receipt_number
from app.domains.members.models import Member
from app.domains.organizations.models import OrganizationSettings

logger = logging.getLogger(__name__)

#: Days from raising a donation receipt to its due date. One, not the seven a
#: membership fee gets: a donation is an impulse paid at a gateway in the next
#: minute, not an invoice with terms. It is not zero either, because the sweep
#: voids on ``due_date < today`` and a donation started late in the evening
#: would otherwise be voidable by the next morning's run while the member was
#: still on the gateway's page.
DONATION_DUE_DAYS = 1

#: The statuses in which a donation receipt is still unpaid, and so can still
#: be abandoned. Mirrors ``OPEN_PURCHASE_STATUSES``: ``paid`` is settled,
#: ``cancelled`` is already gone, and ``returned`` reaches here because a paid
#: receipt is terminal, so a returned one was never really paid.
OPEN_DONATION_STATUSES = ("new", "pending", "emitted", "overdue", "returned")

#: What the receipt line says. A donation has no concept behind it (see
#: ``create_donation``), so this is the only description the member and the PDF
#: get, and it follows the organisation's own locale the way the receipt PDF's
#: labels do.
DONATION_DESCRIPTIONS = {"es": "Donativo", "ca": "Donatiu", "en": "Donation"}


@dataclass(frozen=True)
class DonationOptions:
    """What the donate page may offer, resolved for this instance."""

    message: str | None
    min_amount: int
    max_amount: int
    suggested_amounts: list[int]


def _org(db: Session) -> OrganizationSettings | None:
    return (
        db.query(OrganizationSettings)
        .filter(OrganizationSettings.id == 1)
        .first()
    )


def member_donations_enabled(db: Session) -> bool:
    """Whether this instance offers the donate page at all.

    Absent means off, like every other gate. The endpoints answer 404 on a
    false here rather than 403, so an instance that does not take donations
    does not advertise that the feature exists.
    """
    org = _org(db)
    features = (org.features or {}) if org else {}
    return bool(features.get("member_donations_enabled"))


def donation_amount_bounds(db: Session) -> tuple[int, int]:
    """The configured minimum and maximum, in whole currency units.

    Resolves the pair rather than trusting it. The save-side check can only
    compare the two when a single request carries both (the settings merge is
    sparse), so a row can hold a maximum below its minimum, and the honest
    reading of that is the floor: an administrator who lowered the ceiling past
    the floor has not said "accept nothing".
    """
    org = _org(db)
    features = (org.features or {}) if org else {}
    minimum = billing_int_rule(features, "donation_min_amount")
    maximum = billing_int_rule(features, "donation_max_amount")
    return minimum, max(minimum, maximum)


def suggested_donation_amounts(minimum: int, maximum: int) -> list[int]:
    """A ladder derived from the minimum, not a second thing to configure.

    ``min × 1, 2, 5, 10`` gives 5/10/25/50 on the default minimum of 5, and
    adapts on its own: a village club setting 1 gets 1/2/5/10 and a
    professional association setting 50 gets 50/100/250/500. Anything the
    ceiling excludes is dropped, and the minimum itself always survives because
    the ceiling is never below it.

    Deriving these is a deliberate choice against a third setting. A club that
    wants a different ladder changes its minimum, and a club that wants an
    arbitrary amount types it into the free field, which is the one every
    donation page has anyway.
    """
    ladder = [minimum * step for step in (1, 2, 5, 10)]
    return sorted({amount for amount in ladder if amount <= maximum})


def donation_options(db: Session) -> DonationOptions:
    """Everything the donate page renders, in one read."""
    org = _org(db)
    minimum, maximum = donation_amount_bounds(db)
    return DonationOptions(
        message=(org.donation_message if org else None) or None,
        min_amount=minimum,
        max_amount=maximum,
        suggested_amounts=suggested_donation_amounts(minimum, maximum),
    )


def _assert_amount_allowed(db: Session, amount: Decimal) -> None:
    """Refuse an amount outside the configured bounds.

    Server-side is where this has to hold: the amount arrives from the browser,
    and the bounds exist so that a typo cannot become a 50.000 charge. The form
    mirrors them for the member's sake, not for safety.
    """
    minimum, maximum = donation_amount_bounds(db)
    if amount < minimum or amount > maximum:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "donation_amount_out_of_range",
                "min_amount": minimum,
                "max_amount": maximum,
            },
        )


def create_donation(
    db: Session,
    member: Member,
    amount: Decimal,
    today: date | None = None,
    created_by_id: int | None = None,
) -> Receipt:
    """Raise the receipt for ``member`` donating ``amount``.

    No concept. ``concepts`` is the organisation's chart of the things it
    charges for, and a donation the member chose the size of is not one of
    them; ``origin='donation'`` is what classifies it, which is what #432 gave
    it an origin for. The receipt therefore carries its own description and its
    own amount, which is all the PDF reads.

    VAT is zero, which is the default #432 settled for a donation: there is no
    supply in return for it. An administrator can still raise a taxable
    donation by hand, where there is a counterpart, because that one goes
    through the ordinary receipt endpoints.

    Unlike a membership purchase, an earlier unpaid donation is **not** voided
    by a new one. Two purchases are contradictory — a member holds one plan —
    while two donations are simply two donations, and a member who pays both
    has given twice on purpose. The sweep clears whichever is abandoned.

    Does not commit: the caller owns the transaction.
    """
    today = today or org_today(db)
    _assert_amount_allowed(db, amount)

    org = _org(db)
    locale = (org.locale if org else None) or "es"
    description = DONATION_DESCRIPTIONS.get(locale, DONATION_DESCRIPTIONS["es"])

    receipt = Receipt(
        receipt_number=generate_receipt_number(db, today),
        party_id=member.party_id,
        origin="donation",
        description=description,
        base_amount=amount,
        vat_rate=Decimal("0.00"),
        vat_amount=Decimal("0.00"),
        total_amount=amount,
        status="emitted",
        emission_date=today,
        due_date=today + timedelta(days=DONATION_DUE_DAYS),
        donation_self_service=True,
        # Never collectable by direct debit: the mandate was signed for fees,
        # and a donation inside a remittance is the one state the sweep must
        # leave alone.
        is_batchable=False,
        created_by=created_by_id,
    )
    db.add(receipt)
    db.flush()
    return receipt


def expire_unpaid_donations(db: Session, today: date | None = None) -> int:
    """Void self-service donation receipts nobody paid by their due date.

    An abandoned donation is not a debt. Left open it would be marked overdue
    and then chased for money the member decided not to give, which is the
    wrong message about money that is not owed.

    Four properties, each copied from ``expire_unpaid_purchases`` for the
    reason that one has it:

    - **Before ``mark_overdue``**, on the same ``due_date < today`` boundary, so
      an abandoned donation is voided rather than ever reaching ``overdue``.
    - **Unconditional**, whether or not the club has payment reminders on. An
      abandoned checkout is not a debt regardless of configuration.
    - **Never a receipt in a remittance.** A donation cannot enter one
      (``is_batchable=False``), so this is belt and braces rather than a live
      case — but a receipt handed to the bank must not be voided behind the
      bank's back, and the predicate should say so rather than rely on another
      column staying as it is.
    - **Keyed on ``donation_self_service``, not on ``origin``.** An
      administrator's hand-raised donation receipt is legitimately waiting for
      a bank transfer, and ``origin='donation'`` cannot tell the two apart.

    Returns how many were voided. Does not commit.
    """
    today = today or org_today(db)
    expired = (
        db.query(Receipt)
        .filter(
            Receipt.donation_self_service.is_(True),
            Receipt.is_active.is_(True),
            Receipt.remittance_id.is_(None),
            Receipt.status.in_(OPEN_DONATION_STATUSES),
            Receipt.payment_date.is_(None),
            Receipt.due_date.isnot(None),
            Receipt.due_date < today,
        )
        .all()
    )
    for receipt in expired:
        cancel_receipt(db, receipt)
    return len(expired)
