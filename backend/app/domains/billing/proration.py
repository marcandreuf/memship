"""Proration — what a membership plan costs for the rest of the period it is bought in.

The billing engine is calendar-anchored: ``compute_period`` returns the natural
month, quarter or year, and a ``BillingRun`` is unique per period. A member who
buys mid-period therefore pays for the remainder of that period at purchase and
joins the ordinary cycle with everybody else at the next boundary.

The remainder is counted in **whole months, including the month of purchase**.
A 200 EUR/year plan bought on 15 March covers March to December — 10 of 12
months, 166.67 EUR — not the 160.00 EUR an elapsed-days count would give.
Membership is felt monthly rather than daily, "10 of 12 months" is an invoice
line a treasurer can check by hand, and nobody joining on the 30th pays almost
nothing for a month they used. It also makes the arithmetic immune to month
lengths and leap days: February is a month like any other.

Nothing calls this yet. The purchase endpoint that will is a later phase.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.core.money import round_money
from app.domains.billing.recurring_billing_service import compute_period

# Whole months in one calendar period of each recurring frequency.
MONTHS_IN_PERIOD = {"monthly": 1, "quarterly": 3, "annual": 12}


@dataclass(frozen=True)
class ProratedCharge:
    """What to charge for a plan bought mid-period, and which period it covers.

    ``period_start`` / ``period_end`` are the calendar period the charge covers,
    and a receipt raised from this must be stamped with them: fee generation
    skips a member who already holds a receipt for the same period, so correct
    stamping is what stops the next scheduled run billing the buyer twice.

    Every field but ``amount`` is ``None`` for a ``one_time`` plan, which has no
    calendar period and is never billed again.
    """

    amount: Decimal
    period_start: date | None
    period_end: date | None
    months_charged: int | None
    months_in_period: int | None


def prorate_membership_price(
    base_price: Decimal | None, frequency: str, purchase_date: date
) -> ProratedCharge:
    """The base amount to charge for ``frequency`` bought on ``purchase_date``.

    Pre-tax: VAT is applied to this figure when the receipt is raised, not here.

    ``monthly`` is never prorated — the period is the month of purchase, so the
    whole of it is charged.

    ``one_time`` is supported deliberately rather than left to raise. A plan the
    membership-type API already permits means *pay once, hold indefinitely*: the
    recurring engine excludes it (``is_frequency_due`` is always ``False``), so
    there is no period to prorate against, nothing to stamp on the receipt to
    deduplicate against a later run, and no renewal. The full price is charged.

    Raises ``ValueError`` for any other frequency.
    """
    price = Decimal("0") if base_price is None else Decimal(str(base_price))

    if frequency == "one_time":
        return ProratedCharge(
            amount=round_money(price),
            period_start=None,
            period_end=None,
            months_charged=None,
            months_in_period=None,
        )

    months_in_period = MONTHS_IN_PERIOD.get(frequency)
    if months_in_period is None:
        raise ValueError(f"Unsupported billing frequency: {frequency!r}")

    period_start, period_end = compute_period(frequency, purchase_date)
    months_charged = (
        (period_end.year - purchase_date.year) * 12
        + (period_end.month - purchase_date.month)
        + 1
    )

    return ProratedCharge(
        amount=round_money(price * months_charged / months_in_period),
        period_start=period_start,
        period_end=period_end,
        months_charged=months_charged,
        months_in_period=months_in_period,
    )
