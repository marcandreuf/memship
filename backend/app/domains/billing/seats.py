"""A seat held until its receipt is paid.

A pay-to-confirm seat is a registration today and a space booking tomorrow
(#603). What happens to the seat when its receipt changes is decided here once,
keyed on what the receipt is linked to, and each domain supplies only what is
specific to it. The domains are imported inside the functions because they
build on this package.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domains.billing.models import Receipt


class SeatError(Exception):
    """Raised when a seat cannot take the change asked of it."""


def mark_refund_returned(
    db: Session, seat, user_id: int | None, credit_note_id: int | None = None
) -> None:
    """Record that a refund owed on a seat has been made.

    Moves no money: the club returns it from the gateway's own dashboard, or by
    hand, and records it here. ``seat`` is anything carrying the refund columns
    (a registration today, a booking in #603).
    """
    if seat.refund_status != "due":
        raise SeatError("Only a refund that is due can be marked returned")
    if credit_note_id is not None:
        note = db.query(Receipt).filter(Receipt.id == credit_note_id).first()
        if (
            note is None
            or note.document_type != "credit_note"
            or note.party_id != seat.party_id
        ):
            raise SeatError("Not a credit note issued to this member")
    seat.refund_status = "returned"
    seat.refund_returned_at = datetime.now(timezone.utc)
    seat.refund_returned_by = user_id
    seat.refund_credit_note_id = credit_note_id
    db.flush()


def confirm_paid_seat(db: Session, receipt: Receipt) -> None:
    """Confirm the pending seat this receipt pays for, if it has one.

    A no-op for every receipt that is not linked to a seat, and for a seat that
    is not pending, which is every seat of a ``legacy`` activity.
    """
    if receipt.registration_id is not None:
        from app.domains.activities.registration_service import (
            confirm_pending_registration,
        )

        confirm_pending_registration(db, receipt.registration_id)
