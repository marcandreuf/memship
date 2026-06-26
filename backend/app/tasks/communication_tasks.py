"""Celery tasks for the communications domain."""

import logging

from app.core.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def send_announcement_task(self, announcement_id: int) -> int:
    """Fan out an announcement email to its resolved audience.

    Triggered on Send (no Beat entry). Notification rows are written
    synchronously in the service; only the email fan-out is async.
    Returns the number of emails sent.
    """
    try:
        from app.core.email import send_announcement_email
        from app.db.session import SessionLocal
        from app.domains.communications.markdown import render_markdown
        from app.domains.communications.models import Announcement
        from app.domains.communications.service import (
            email_recipients,
            resolve_audience,
        )
        from app.domains.organizations.models import OrganizationSettings

        db = SessionLocal()
        try:
            ann = (
                db.query(Announcement)
                .filter(Announcement.id == announcement_id)
                .first()
            )
            if not ann:
                logger.warning(f"Announcement {announcement_id} not found for email")
                return 0

            org = (
                db.query(OrganizationSettings)
                .filter(OrganizationSettings.id == 1)
                .first()
            )
            locale = (org.locale if org else None) or "es"
            org_name = (org.name if org else None) or "Memship"
            body_html = render_markdown(ann.body)

            members = resolve_audience(db, ann.target_type, ann.target_id)
            sent = 0
            for person in email_recipients(db, members):
                if send_announcement_email(
                    person.email, ann.subject, body_html, org_name, locale
                ):
                    sent += 1
            logger.info(f"Announcement {announcement_id}: {sent} emails sent")
            return sent
        finally:
            db.close()
    except Exception as exc:
        logger.error(f"Announcement email task failed: id={announcement_id}, error={exc}")
        raise self.retry(exc=exc)
