"""Billing a space booking — what it costs, and the receipt that follows.

The rule is the one activities already follow: *bill once, bill on every
confirmation path, void on cancel.* A confirmed booking in a paid space is money
owed whichever path produced it, so both ``create_booking`` and waitlist
promotion come through :func:`ensure_booking_receipt`.

Price lives on the ``Space`` as the default and on the ``SpaceSlot`` as an
optional override, so a club sets one number for "the court costs 10 €" and only
reaches for the override when prime time costs more. A slot's own ``0`` is an
explicit free slot in a paid space, which is why the override is read by
``is not None`` and not by truthiness.

Nothing here is a refund path. There is none: a member who cancels a paid
booking keeps the invoice unless it was still unpaid, and one whose slot an
admin deletes is in exactly the same position. Cancelling voids what has not
been paid and leaves a paid receipt standing, to be settled offline.
"""

import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domains.bookings.models import Booking, Space, SpaceSlot

logger = logging.getLogger(__name__)

#: Receipt statuses a cancellation may void — everything short of paid.
VOIDABLE_STATUSES = ("new", "pending", "emitted", "overdue")


def booking_price(space: Space, slot: SpaceSlot) -> Decimal:
    """What this slot costs: its own price, or the space's, or nothing."""
    amount = slot.price if slot.price is not None else space.price
    return Decimal(str(amount)) if amount is not None else Decimal("0")


def booking_description(space: Space, slot: SpaceSlot) -> str:
    """The line the member is invoiced for.

    Self-contained on purpose. ``Receipt.booking_id`` is ``ON DELETE SET NULL``,
    so this text is all that survives an admin deleting the slot.
    """
    times = (
        f"{slot.start_time.strftime('%H:%M')}–{slot.end_time.strftime('%H:%M')}"
    )
    return f"{space.name} — {slot.slot_date.strftime('%d/%m/%Y')} {times}"


def ensure_booking_receipt(
    db: Session, booking: Booking, slot: SpaceSlot, space: Space
) -> None:
    """Bill a confirmed booking, once.

    Idempotent: a booking that already has a live receipt keeps it, so a member
    promoted after re-joining a waitlist is not billed twice. A receipt voided by
    an earlier cancellation deliberately does not count as live — re-booking owes
    money again.

    Free stays free with no special-casing: a space with no price, or a slot
    overriding it to zero, produces no receipt at all.

    Receipt generation never fails the booking. The seat has already been given,
    and rolling it back here would be worse than an invoice an admin has to raise
    by hand — so the error is logged and the booking stands.
    """
    amount = booking_price(space, slot)
    if amount <= 0:
        return

    from app.domains.billing.models import Receipt

    # The receipt a cancellation just voided may still be pending in the session
    # (the app's sessions do not autoflush), and it must not read as a live one.
    db.flush()
    existing = (
        db.query(Receipt)
        .filter(
            Receipt.booking_id == booking.id,
            Receipt.is_active.is_(True),
            Receipt.status != "cancelled",
        )
        .first()
    )
    if existing:
        return

    try:
        from app.domains.billing.service import generate_booking_receipt

        # Best-effort, inside a SAVEPOINT so a failure rolls back only the
        # receipt and leaves the booking's transaction usable.
        with db.begin_nested():
            generate_booking_receipt(
                db=db,
                booking_id=booking.id,
                member_id=booking.member_id,
                description=booking_description(space, slot),
                amount=amount,
            )
    except Exception as exc:
        logger.error(
            "Failed to generate receipt for booking %s: %s", booking.id, exc
        )


def void_booking_receipts(db: Session, booking: Booking) -> None:
    """Void the unpaid receipts of a cancelled booking; leave a paid one alone.

    A paid receipt stays paid because the system has no way to represent a
    refund — there are no credit notes and no refund API — so the club settles
    it offline. Voiding it here would silently erase money that changed hands.
    """
    from app.domains.billing.models import Receipt
    from app.domains.billing.service import cancel_receipt

    try:
        receipts = (
            db.query(Receipt)
            .filter(
                Receipt.booking_id == booking.id,
                Receipt.is_active.is_(True),
                Receipt.status.in_(VOIDABLE_STATUSES),
            )
            .all()
        )
        for receipt in receipts:
            cancel_receipt(db, receipt)
    except Exception:
        # The seat is already released, so failing the cancellation here would
        # be worse than an invoice left open — but it must not be invisible. A
        # receipt still standing against a cancelled booking is money the member
        # is asked for and does not owe.
        logger.exception(
            "Failed to void receipts for booking %s; a receipt may still stand "
            "against a cancelled booking",
            booking.id,
        )
