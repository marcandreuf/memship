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
    """Log an incoming webhook event. Returns None if it is a settled duplicate.

    Uses a savepoint so that a duplicate IntegrityError doesn't
    invalidate the outer transaction.

    A redelivery of an event whose stored row is ``failed`` is *not* treated as a
    duplicate: it is reset to ``received`` and returned, so the caller runs the
    handler again. Both Stripe and Redsys retry after a 5xx, and short-circuiting
    those retries on the unique constraint meant a payment that failed to apply
    once — a lock timeout, a transient DB error — was never applied at all, while
    the provider was told 200 OK. The row is locked FOR UPDATE first so two
    simultaneous retries cannot both claim it.
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
        return _claim_failed_event(db, external_event_id, event_type, payload)
    return event


def _claim_failed_event(
    db: Session, external_event_id: str, event_type: str, payload: dict
) -> WebhookEvent | None:
    """Return the stored event for reprocessing if it previously failed, else None."""
    existing = (
        db.query(WebhookEvent)
        .filter(WebhookEvent.external_event_id == external_event_id)
        .with_for_update()
        .first()
    )
    if existing is None or existing.status != "failed":
        return None

    existing.event_type = event_type
    existing.payload = payload
    existing.status = "received"
    existing.error_message = None
    existing.processed_at = None
    db.flush()
    return existing


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
