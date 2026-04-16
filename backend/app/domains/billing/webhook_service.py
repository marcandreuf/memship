"""Webhook event service — logging, deduplication, status tracking."""

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domains.billing.models import WebhookEvent


def log_event(
    db: Session,
    provider_type: str,
    external_event_id: str,
    event_type: str,
    payload: dict,
) -> WebhookEvent | None:
    """Log an incoming webhook event. Returns None if duplicate.

    Uses a savepoint so that a duplicate IntegrityError doesn't
    invalidate the outer transaction.
    """
    event = WebhookEvent(
        provider_type=provider_type,
        external_event_id=external_event_id,
        event_type=event_type,
        payload=payload,
        status="received",
    )
    nested = db.begin_nested()
    db.add(event)
    try:
        nested.commit()
    except IntegrityError:
        nested.rollback()
        return None
    return event


def mark_processed(
    db: Session, event: WebhookEvent, receipt_id: int | None = None
) -> None:
    """Mark a webhook event as successfully processed."""
    event.status = "processed"
    event.receipt_id = receipt_id
    event.processed_at = datetime.now(timezone.utc)
    db.flush()


def mark_failed(db: Session, event: WebhookEvent, error: str) -> None:
    """Mark a webhook event as failed."""
    event.status = "failed"
    event.error_message = error
    event.processed_at = datetime.now(timezone.utc)
    db.flush()


def mark_ignored(db: Session, event: WebhookEvent, reason: str) -> None:
    """Mark a webhook event as ignored (e.g. stale or out-of-order)."""
    event.status = "ignored"
    event.error_message = reason
    event.processed_at = datetime.now(timezone.utc)
    db.flush()


def is_duplicate(db: Session, external_event_id: str) -> bool:
    """Check if an event with this external ID already exists."""
    return (
        db.query(WebhookEvent)
        .filter(WebhookEvent.external_event_id == external_event_id)
        .first()
        is not None
    )
