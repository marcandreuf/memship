"""Celery tasks for asynchronous email sending."""

import logging

from app.core.celery_app import celery
from app.core.email import (
    send_email,
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
