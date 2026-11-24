"""What the pay-to-confirm flow asks of a space booking (#603).

The activity flow's counterpart, with one difference that shapes everything
here: a booking is for one slot on one date, often tomorrow. So every pending
booking has a deadline, ``slot start − cut-off``, and auto-cancel can only bring
it earlier. A booking never reaches its slot still pending.

A ``legacy`` space never reaches anything here but ``needs_payment``, which is
false for it.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.clock import org_timezone
from app.domains.activities.models import PAYMENT_FLOW_PAY_TO_CONFIRM
from app.domains.billing.payment_instructions import (
    seat_payment_instructions,
    transfer_reference,
)
from app.domains.bookings.models import Space, SpaceSlot
from app.domains.bookings.rules import int_rule
from app.domains.organizations.models import OrganizationSettings


def needs_payment(space: Space, amount: Decimal | None) -> bool:
    """Whether a booking at ``amount`` is held as pending until paid.

    The one place the flow branches: a ``legacy`` space and a free slot are
    booked at once, as before.
    """
    return (
        space.payment_flow == PAYMENT_FLOW_PAY_TO_CONFIRM
        and amount is not None
        and Decimal(str(amount)) > 0
    )


def _features(db: Session) -> dict:
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    return (org.features if org else None) or {}


def auto_cancel_hours(db: Session, space: Space) -> int | None:
    """How long an unpaid booking may be held before its cut-off, or None when
    auto-cancel is off. The space's override wins; NULL inherits the club's."""
    features = _features(db)
    enabled = space.auto_cancel_enabled
    if enabled is None:
        enabled = features.get("booking_auto_cancel_enabled") is True
    if not enabled:
        return None
    if space.auto_cancel_hours is not None:
        return space.auto_cancel_hours
    return int_rule(features, "booking_auto_cancel_hours")


def slot_start(db: Session, slot: SpaceSlot) -> datetime:
    return datetime.combine(slot.slot_date, slot.start_time, tzinfo=org_timezone(db))


def payment_deadline(
    db: Session, space: Space, slot: SpaceSlot, now: datetime
) -> datetime:
    """When a booking held from ``now`` must be paid by.

    The slot's start less the club's cut-off, or ``now`` plus the auto-cancel
    hours when that comes first.
    """
    cutoff = slot_start(db, slot) - timedelta(
        minutes=int_rule(_features(db), "booking_payment_cutoff_minutes")
    )
    hours = auto_cancel_hours(db, space)
    if hours is None:
        return cutoff
    return min(cutoff, now + timedelta(hours=hours))


def min_hold(db: Session) -> timedelta:
    """The shortest hold the club offers; a booking that would get less is refused."""
    return timedelta(minutes=int_rule(_features(db), "booking_min_hold_minutes"))


def auto_promotion_min(db: Session) -> timedelta:
    """The shortest hold for which a freed seat goes to the next waitlister by
    itself. A member promoted unawares may not see it in time; one who books by
    hand is in front of the screen and can pay at once."""
    return timedelta(
        minutes=int_rule(_features(db), "booking_auto_promotion_min_minutes")
    )


def cutoff_minutes(db: Session) -> int:
    return int_rule(_features(db), "booking_payment_cutoff_minutes")


def booking_payment_details(
    db: Session, booking, space: Space, receipt, locale: str
) -> dict:
    """What a mail about a booking held until paid tells the member: the amount,
    the deadline and the ways this space accepts."""
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    instructions = seat_payment_instructions(db, space, locale)
    return dict(
        amount=f"{receipt.total_amount:.2f}",
        currency=(org.currency if org else None) or "EUR",
        deadline=booking.payment_due_at.astimezone(org_timezone(db)).strftime(
            "%d/%m/%Y %H:%M"
        ),
        pay_now_url=instructions.pay_now_url,
        bank_details=instructions.bank_details,
        cash=instructions.cash,
        reference=transfer_reference(receipt) if instructions.bank_details else None,
    )


def seat_offer_details(
    db: Session, space: Space, slot: SpaceSlot, pay_by: datetime, locale: str
) -> dict:
    """What the mail offering a freed seat to the waiting list says: what it
    costs, by when a booking made now must be paid, and where to book it."""
    from app.core.config import settings
    from app.domains.billing.service import calculate_vat, org_default_vat_rate
    from app.domains.bookings.billing import booking_price

    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    _, total = calculate_vat(booking_price(space, slot), org_default_vat_rate(org))
    return dict(
        amount=f"{total:.2f}",
        currency=(org.currency if org else None) or "EUR",
        deadline=pay_by.astimezone(org_timezone(db)).strftime("%d/%m/%Y %H:%M"),
        book_url=(
            f"{settings.FRONTEND_URL}/{locale}/book"
            f"?space={space.id}&date={slot.slot_date.isoformat()}"
        ),
    )
