"""Booking notifications — a swappable port for confirmation/waitlist emails.

The service depends only on ``BookingNotifier``. The concrete
``EmailBookingNotifier`` renders templates and dispatches through the existing
email infrastructure (Celery → SMTP/Resend). The SSO work introduces a unified
email-delivery system that will replace ``EmailBookingNotifier`` with no change
to the service or the templates. A send/dispatch failure is logged and never
propagates — it must not roll back a booking or a promotion.
"""

import logging
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from app.db.after_commit import run_after_commit

logger = logging.getLogger(__name__)


@dataclass
class BookingNotification:
    """Everything an email backend needs, resolved by the service."""

    to: str | None
    member_name: str
    space_name: str
    date_str: str
    time_str: str
    locale: str = "es"
    position: int | None = None
    cancellation_deadline_hours: int | None = None
    # The amount, deadline and ways to pay of a booking held until paid.
    payment: dict | None = None
    # A paid booking cancelled without keeping the payment owes it back.
    refund_due: bool = False


class BookingNotifier(Protocol):
    def send_confirmation(self, note: BookingNotification) -> None: ...

    def send_pending_payment(self, note: BookingNotification) -> None: ...

    def send_waitlisted(self, note: BookingNotification) -> None: ...

    def send_promoted(self, note: BookingNotification) -> None: ...

    def send_admin_cancellation(self, note: BookingNotification) -> None: ...


class EmailBookingNotifier:
    """Dispatches booking emails asynchronously via Celery. Never raises.

    Given a session, each mail is queued for after that session commits, so a
    change that rolls back tells nobody. A path that runs outside a booking
    request, like a payment confirming a booking, passes one.
    """

    def __init__(self, db: Session | None = None):
        self._db = db

    def send_confirmation(self, note: BookingNotification) -> None:
        self._dispatch("confirmation", note)

    def send_pending_payment(self, note: BookingNotification) -> None:
        self._dispatch("pending_payment", note)

    def send_waitlisted(self, note: BookingNotification) -> None:
        self._dispatch("waitlisted", note)

    def send_promoted(self, note: BookingNotification) -> None:
        self._dispatch("promoted", note)

    def send_admin_cancellation(self, note: BookingNotification) -> None:
        # One template covers all admin-initiated cases: single cancel, slot
        # removal, space removal.
        self._dispatch("cancelled", note)

    def _dispatch(self, kind: str, note: BookingNotification) -> None:
        if not note.to:
            return
        try:
            from app.tasks.email_tasks import send_booking_email_task

            payload = dict(
                kind=kind,
                to=note.to,
                member_name=note.member_name,
                space_name=note.space_name,
                date_str=note.date_str,
                time_str=note.time_str,
                locale=note.locale,
                position=note.position,
                cancellation_deadline_hours=note.cancellation_deadline_hours,
                payment=note.payment,
                refund_due=note.refund_due,
            )
            send = lambda: send_booking_email_task.delay(**payload)  # noqa: E731
            if self._db is not None:
                run_after_commit(self._db, send)
            else:
                send()
        except Exception as exc:  # dispatch must never break the booking
            logger.error(f"Failed to dispatch booking {kind} email: {exc}")


class NullBookingNotifier:
    """No-op notifier (tests, or environments with notifications off)."""

    def send_confirmation(self, note: BookingNotification) -> None: ...

    def send_pending_payment(self, note: BookingNotification) -> None: ...

    def send_waitlisted(self, note: BookingNotification) -> None: ...

    def send_promoted(self, note: BookingNotification) -> None: ...

    def send_admin_cancellation(self, note: BookingNotification) -> None: ...
