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


class BookingNotifier(Protocol):
    def send_confirmation(self, note: BookingNotification) -> None: ...

    def send_waitlisted(self, note: BookingNotification) -> None: ...

    def send_promoted(self, note: BookingNotification) -> None: ...

    def send_admin_cancellation(self, note: BookingNotification) -> None: ...


class EmailBookingNotifier:
    """Dispatches booking emails asynchronously via Celery. Never raises."""

    def send_confirmation(self, note: BookingNotification) -> None:
        self._dispatch("confirmation", note)

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

            send_booking_email_task.delay(
                kind=kind,
                to=note.to,
                member_name=note.member_name,
                space_name=note.space_name,
                date_str=note.date_str,
                time_str=note.time_str,
                locale=note.locale,
                position=note.position,
                cancellation_deadline_hours=note.cancellation_deadline_hours,
            )
        except Exception as exc:  # dispatch must never break the booking
            logger.error(f"Failed to dispatch booking {kind} email: {exc}")


class NullBookingNotifier:
    """No-op notifier (tests, or environments with notifications off)."""

    def send_confirmation(self, note: BookingNotification) -> None: ...

    def send_waitlisted(self, note: BookingNotification) -> None: ...

    def send_promoted(self, note: BookingNotification) -> None: ...

    def send_admin_cancellation(self, note: BookingNotification) -> None: ...
