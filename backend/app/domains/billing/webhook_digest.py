"""The daily email telling the administrator which payment notifications went wrong (#514).

A failed or ignored notification — including a second charge for a receipt
already paid — and a run of notifications refused at the signature check all
wait silently to be looked for. This collects the last day's into one email to
the billing notification address, sent only when there is something in it.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, joinedload

from app.domains.billing import webhook_rejections
from app.domains.billing.models import PaymentProvider, WebhookEvent

WINDOW = timedelta(hours=24)
# The email names this many events and counts the rest; the admin view lists all.
MAX_LISTED = 20


@dataclass(frozen=True)
class WebhookDigest:
    events: list[dict]
    events_total: int
    rejections: list[dict]

    @property
    def is_empty(self) -> bool:
        return self.events_total == 0 and not self.rejections


def build_digest(db: Session, now: datetime, tz_name: str | None = None) -> WebhookDigest:
    since = now - WINDOW
    tz = _zone(tz_name)

    query = (
        db.query(WebhookEvent)
        .options(joinedload(WebhookEvent.receipt))
        .filter(
            WebhookEvent.status.in_(("failed", "ignored")),
            WebhookEvent.created_at >= since,
        )
    )
    total = query.count()
    listed = query.order_by(WebhookEvent.created_at.desc(), WebhookEvent.id.desc()).limit(
        MAX_LISTED
    )
    events = [
        {
            "at": _local(e.created_at, tz),
            "provider": e.provider_type,
            "event_type": e.event_type,
            "status": e.status,
            "reason": e.error_message or "",
            "receipt_number": e.receipt.receipt_number if e.receipt else None,
        }
        for e in listed
    ]

    provider_types = [t for (t,) in db.query(PaymentProvider.provider_type).distinct()]
    summaries = webhook_rejections.rejection_summaries(provider_types, since) or []
    rejections = [
        {
            "provider": s.provider_type,
            "count": s.count,
            "last_at": _local(s.last_at, tz) if s.last_at else "",
            "last_reason": s.last_reason or "",
        }
        for s in summaries
    ]
    return WebhookDigest(events=events, events_total=total, rejections=rejections)


def _zone(tz_name: str | None):
    try:
        return ZoneInfo(tz_name) if tz_name else timezone.utc
    except (KeyError, ValueError):
        return timezone.utc


def _local(moment: datetime, tz) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(tz).strftime("%Y-%m-%d %H:%M")
