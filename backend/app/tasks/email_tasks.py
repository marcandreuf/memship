"""Celery tasks for asynchronous email sending."""

import logging

from app.core.celery_app import celery
from app.core.email import (
    send_email,
    send_email_with_attachment,
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

            # Generate PDF
            pdf_bytes = generate_receipt_pdf(db, receipt)

            # Build subject
            subjects = {
                "es": f"Recibo {receipt.receipt_number} — {org.name}",
                "ca": f"Rebut {receipt.receipt_number} — {org.name}",
                "en": f"Receipt {receipt.receipt_number} — {org.name}",
            }
            subject = subjects.get(locale, subjects["es"])

            # Build simple HTML body
            bodies = {
                "es": f"<p>Adjunto el recibo <strong>{receipt.receipt_number}</strong> por importe de <strong>{receipt.total_amount:.2f} {org.currency or 'EUR'}</strong>.</p>",
                "ca": f"<p>Adjunt el rebut <strong>{receipt.receipt_number}</strong> per import de <strong>{receipt.total_amount:.2f} {org.currency or 'EUR'}</strong>.</p>",
                "en": f"<p>Please find attached receipt <strong>{receipt.receipt_number}</strong> for <strong>{receipt.total_amount:.2f} {org.currency or 'EUR'}</strong>.</p>",
            }
            html_body = bodies.get(locale, bodies["es"])

            return send_email_with_attachment(
                to=person.email,
                subject=subject,
                html_body=html_body,
                attachment=pdf_bytes,
                attachment_filename=f"{receipt.receipt_number}.pdf",
                attachment_mime="application/pdf",
            )
        finally:
            db.close()
    except Exception as exc:
        logger.error(f"Receipt email task failed: receipt_id={receipt_id}, error={exc}")
        raise self.retry(exc=exc)
