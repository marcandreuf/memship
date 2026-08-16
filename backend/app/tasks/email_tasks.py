"""Celery tasks for asynchronous email sending."""

import logging

from app.core.celery_app import celery
from app.core.email import (
    send_booking_cancelled_email,
    send_booking_confirmation_email,
    send_booking_promoted_email,
    send_booking_waitlisted_email,
    send_email,
    send_receipt_delivery_email,
    send_registration_confirmation_email,
    send_registration_cancellation_email,
    send_waitlist_promotion_email,
)

logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_task(self, to: str, subject: str, html_body: str) -> bool:
    """Send a generic email asynchronously."""
    try:
        return send_email(to, subject, html_body)
    except Exception as exc:
        logger.error(f"Email task failed: to={to}, error={exc}")
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def send_registration_email_task(
    self,
    to: str,
    member_name: str,
    activity_name: str,
    status: str,
    activity_date: str | None = None,
    location: str | None = None,
    locale: str = "es",
) -> bool:
    """Send registration confirmation/waitlist email."""
    try:
        return send_registration_confirmation_email(
            to, member_name, activity_name, status, activity_date, location, locale,
        )
    except Exception as exc:
        logger.error(f"Registration email task failed: to={to}, error={exc}")
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def send_cancellation_email_task(
    self,
    to: str,
    member_name: str,
    activity_name: str,
    cancelled_by: str | None = None,
    locale: str = "es",
) -> bool:
    """Send registration cancellation email."""
    try:
        return send_registration_cancellation_email(
            to, member_name, activity_name, cancelled_by, locale,
        )
    except Exception as exc:
        logger.error(f"Cancellation email task failed: to={to}, error={exc}")
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def send_promotion_email_task(
    self,
    to: str,
    member_name: str,
    activity_name: str,
    activity_date: str | None = None,
    location: str | None = None,
    locale: str = "es",
) -> bool:
    """Send waitlist promotion email."""
    try:
        return send_waitlist_promotion_email(
            to, member_name, activity_name, activity_date, location, locale,
        )
    except Exception as exc:
        logger.error(f"Promotion email task failed: to={to}, error={exc}")
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def send_booking_email_task(
    self,
    kind: str,
    to: str,
    member_name: str,
    space_name: str,
    date_str: str,
    time_str: str,
    locale: str = "es",
    position: int | None = None,
    cancellation_deadline_hours: int | None = None,
) -> bool:
    """Send a booking confirmation / waitlisted / promoted email."""
    try:
        if kind == "confirmation":
            return send_booking_confirmation_email(
                to, member_name, space_name, date_str, time_str,
                cancellation_deadline_hours, locale,
            )
        if kind == "waitlisted":
            return send_booking_waitlisted_email(
                to, member_name, space_name, date_str, time_str, position, locale,
            )
        if kind == "promoted":
            return send_booking_promoted_email(
                to, member_name, space_name, date_str, time_str, locale,
            )
        if kind == "cancelled":
            return send_booking_cancelled_email(
                to, member_name, space_name, date_str, time_str, locale,
            )
        logger.error(f"Unknown booking email kind: {kind}")
        return False
    except Exception as exc:
        logger.error(f"Booking email task failed: to={to}, kind={kind}, error={exc}")
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def send_receipt_email_task(self, receipt_id: int) -> bool:
    """Generate receipt PDF and send it by email to the member."""
    try:
        from app.db.session import SessionLocal
        from app.domains.billing.models import Receipt
        from app.domains.billing.pdf import generate_receipt_pdf
        from app.domains.members.models import Member
        from app.domains.organizations.models import OrganizationSettings
        from app.domains.persons.models import Person

        db = SessionLocal()
        try:
            receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
            if not receipt:
                logger.warning(f"Receipt {receipt_id} not found for email")
                return False

            member = db.query(Member).filter(Member.id == receipt.member_id).first()
            if not member:
                logger.warning(f"Member {receipt.member_id} not found for receipt email")
                return False

            person = db.query(Person).filter(Person.id == member.person_id).first()
            if not person or not person.email:
                logger.warning(f"No email for member {member.id}")
                return False

            org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
            locale = org.locale or "es"

            pdf_bytes = generate_receipt_pdf(db, receipt)

            return send_receipt_delivery_email(
                to=person.email,
                member_name=person.first_name,
                receipt_number=receipt.receipt_number,
                amount=f"{receipt.total_amount:.2f}",
                currency=org.currency or "EUR",
                org_name=org.name,
                pdf_bytes=pdf_bytes,
                locale=locale,
            )
        finally:
            db.close()
    except Exception as exc:
        logger.error(f"Receipt email task failed: receipt_id={receipt_id}, error={exc}")
        raise self.retry(exc=exc)
