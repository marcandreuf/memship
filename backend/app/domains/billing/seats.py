"""A seat held until its receipt is paid.

A pay-to-confirm seat is a registration today and a space booking tomorrow
(#603). What happens to the seat when its receipt changes is decided here once,
keyed on what the receipt is linked to, and each domain supplies only what is
specific to it. The domains are imported inside the functions because they
build on this package.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.after_commit import run_after_commit
from app.domains.billing.models import Receipt
from app.domains.organizations.models import OrganizationSettings

logger = logging.getLogger(__name__)

# Receipt statuses that still ask for money.
UNPAID_RECEIPT_STATUSES = ("new", "pending", "emitted", "overdue")


class SeatError(Exception):
    """Raised when a seat cannot take the change asked of it.

    ``detail`` is what the API answers: the English message, or with a
    ``code`` the ``{"code", ..., "message"}`` shape the UI translates.
    """

    def __init__(self, message: str, code: str | None = None, **fields):
        super().__init__(message)
        self.detail = {"code": code, **fields, "message": message} if code else message


#: The mails that tell a member their activity seat is held until paid, about to
#: be released, and released. Operational, and off unless the club switched them
#: on. Each domain has its own, worded for what is held (#603).
SEAT_PAYMENT_TEMPLATES = (
    "registration_pending_payment",
    "payment_deadline_reminder",
    "registration_cancelled_unpaid",
)


def switched_off_seat_templates(
    db: Session, templates: tuple[str, ...] = SEAT_PAYMENT_TEMPLATES
) -> list[str]:
    """Which of a domain's seat-payment mails the club has switched off."""
    from app.domains.mailing.policy import is_enabled

    return [key for key in templates if not is_enabled(db, key)]


def refuse_auto_cancel_without_notices(
    db: Session, templates: tuple[str, ...] = SEAT_PAYMENT_TEMPLATES
) -> None:
    """Auto-cancel releases a seat its holder may not know is at risk. It may
    only be switched on while every mail that warns them is on."""
    off = switched_off_seat_templates(db, templates)
    if off:
        raise SeatError(
            "Auto-cancel needs these emails switched on first: " + ", ".join(off),
            code="auto_cancel_needs_emails",
            templates=off,
        )


def required_seat_templates(db: Session) -> set[str]:
    """The seat-payment mails the club may not switch off right now: those of
    every domain that can release a seat for non-payment."""
    required: set[str] = set()
    if auto_cancel_in_use(db):
        required.update(SEAT_PAYMENT_TEMPLATES)
    return required


def receipt_due_date(db: Session, due_at: datetime | None) -> date:
    """The seat's deadline, as a date in the club's timezone; without one, the
    club's usual due days."""
    from app.core.clock import org_timezone, org_today
    from app.domains.billing.recurring_billing_service import membership_fee_due_days

    if due_at is not None:
        return due_at.astimezone(org_timezone(db)).date()
    return org_today(db) + timedelta(days=membership_fee_due_days(db))


def auto_cancel_in_use(db: Session) -> bool:
    """Whether some seat can be released for non-payment: the club default is
    on, or a live pay-to-confirm activity switched it on for itself."""
    from app.domains.activities.models import Activity

    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if ((org.features if org else None) or {}).get("activity_auto_cancel_enabled") is True:
        return True
    return (
        db.query(Activity.id)
        .filter(
            Activity.payment_flow == "pay_to_confirm",
            Activity.auto_cancel_enabled.is_(True),
            Activity.status.in_(("draft", "published")),
        )
        .first()
        is not None
    )


@dataclass(frozen=True)
class LateSeat:
    """What a domain reports back after settling a late payment on its seat."""

    confirmed: bool
    name: str
    member_name: str | None


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
    is not pending, which is every seat of a ``legacy`` activity or space.
    """
    if receipt.registration_id is not None:
        from app.domains.activities.registration_service import (
            confirm_pending_registration,
        )

        confirm_pending_registration(db, receipt.registration_id)
    elif receipt.booking_id is not None:
        from app.domains.bookings.notifications import EmailBookingNotifier
        from app.domains.bookings.service import confirm_pending_booking

        confirm_pending_booking(
            db, receipt.booking_id, notifier=EmailBookingNotifier(db)
        )


def record_late_payment(db: Session, receipt: Receipt, **payment) -> list[int] | None:
    """A gateway paid a receipt we had cancelled because its seat was released.

    The money has moved, so it is recorded: the one, narrow exception to
    ``cancelled`` being terminal. Only a receipt linked to a seat, and only from
    the gateway webhooks — ``VALID_TRANSITIONS`` is untouched, so nothing else
    can reopen a cancelled receipt. It is reinstated and paid through
    ``mark_receipt_paid`` like any payment, so the books show money received.
    The seat's domain then gives the seat back if one is free, or owes the money
    back, and the club is alerted either way.

    ``payment`` is what ``mark_receipt_paid`` takes. Returns the receipts to
    notify, or None when the receipt is not a seat's and stays ignored.
    """
    if receipt.status != "cancelled" or receipt.registration_id is None:
        return None

    from app.domains.activities.registration_service import settle_late_payment
    from app.domains.billing.service import mark_receipt_paid

    receipt.status = "emitted"
    notify = mark_receipt_paid(db, receipt, **payment)
    seat = settle_late_payment(db, receipt)
    _dispatch_late_payment_alert(db, receipt, seat)
    # "Payment received, nothing more to do" would tell a member without a seat
    # they have one; the seat's domain has told them the money goes back instead.
    return notify if seat.confirmed else []


def _dispatch_late_payment_alert(db: Session, receipt: Receipt, seat) -> None:
    """Queue the club's alert for after commit: urgent, since only the club can
    return the money, from the gateway's own dashboard."""
    from app.tasks.email_tasks import send_late_payment_alert_email_task

    try:
        org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
        features = (org.features if org else None) or {}
        to = features.get("billing_notification_email") or (org.email if org else None)
        if not to:
            logger.error(
                "Late payment on receipt %s and no club address to alert", receipt.id
            )
            return
        payload = dict(
            to=to,
            member_name=seat.member_name,
            seat_name=seat.name,
            amount=f"{receipt.total_amount:.2f}",
            currency=(org.currency if org else None) or "EUR",
            receipt_number=receipt.receipt_number,
            gateway=receipt.payment_method,
            seat_confirmed=seat.confirmed,
            locale=(org.locale if org else None) or "es",
        )
        run_after_commit(db, lambda: send_late_payment_alert_email_task.delay(**payload))
    except Exception:
        logger.exception("Failed to dispatch late payment alert for receipt %s", receipt.id)


def void_unpaid_receipts(db: Session, link_column, seat_id: int) -> None:
    """Cancel every receipt of a seat that still asks for money.

    ``link_column`` is the receipt's link to the seat (``Receipt.registration_id``
    or ``Receipt.booking_id``). A paid receipt is left alone: what to do with
    money already received is ``refund_status``'s business, not this function's.

    Invoices only: a credit note carries its invoice's link too, and is as final
    as the invoice it rectifies. Each goes through ``cancel_receipt``, so one
    sitting in a remittance still being assembled leaves it rather than being
    collected anyway (#383). One the bank is already collecting cannot be
    cancelled; it is logged and the rest are still voided.
    """
    from app.domains.billing.service import cancel_receipt

    for receipt in (
        db.query(Receipt)
        .filter(
            link_column == seat_id,
            Receipt.is_active.is_(True),
            Receipt.document_type == "invoice",
            Receipt.status.in_(UNPAID_RECEIPT_STATUSES),
        )
        .all()
    ):
        try:
            cancel_receipt(db, receipt)
        except HTTPException:
            logger.error(
                "Receipt %s of a released seat is being collected and stays live",
                receipt.id,
            )


def expire_unpaid_seats(db: Session, now: datetime | None = None) -> int:
    """Cancel every pending seat whose payment deadline has passed.

    Every five minutes, because a booking's deadline can fall an hour before its
    slot (#603), and also at the start of the daily dunning pass, so an expiring seat's receipt is voided rather than
    ever reaching ``mark_overdue``. Each domain says which of its seats are past
    their deadline and how to cancel one, which voids its receipt and gives the
    seat to the next in line.

    Returns how many seats were cancelled. Does not commit.
    """
    from app.domains.activities.registration_service import (
        expire_unpaid_registration,
        expired_pending_registrations,
    )

    from app.domains.bookings.notifications import EmailBookingNotifier
    from app.domains.bookings.service import (
        expire_unpaid_booking,
        expired_pending_bookings,
    )

    now = now or datetime.now(timezone.utc)
    expired = expired_pending_registrations(db, now)
    for registration in expired:
        expire_unpaid_registration(db, registration)
    bookings = expired_pending_bookings(db, now)
    notifier = EmailBookingNotifier(db)
    for booking in bookings:
        expire_unpaid_booking(db, booking, notifier=notifier)
    return len(expired) + len(bookings)


def remind_unpaid_seats(db: Session) -> int:
    """Warn, once, each holder of a pending seat whose deadline is near.

    Each domain decides when its seats are near enough. Returns how many were
    warned. Does not commit.
    """
    from app.domains.activities.registration_service import remind_pending_deadlines
    from app.domains.bookings.notifications import EmailBookingNotifier
    from app.domains.bookings.service import remind_booking_deadlines

    return remind_pending_deadlines(db) + remind_booking_deadlines(
        db, datetime.now(timezone.utc), notifier=EmailBookingNotifier(db)
    )
