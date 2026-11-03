"""Payment notifications refused before they could be recorded (#514).

A notification that fails signature verification cannot become a
``webhook_events`` row: its event id comes from an unverified body, and an
unauthenticated caller must not be able to write a database row per request.
So the attempt is counted in Redis instead — the Redis the auth throttles and
Celery already use — as a capped, expiring sorted set of times per provider,
plus the last reason. Enough to tell an administrator "Stripe has refused 40
notifications since yesterday: invalid signature", which is the signal that a
webhook secret is wrong; never enough to grow without bound under a flood.

Best-effort throughout: Redis being down must not change how the webhook
answers, so a failure is logged and the count is reported as unavailable.
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import cache

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

KEY_PREFIX = "memship:webhook-rejections"
RETENTION_SECONDS = 30 * 24 * 3600
MAX_TRACKED = 1000
REASON_MAX_LENGTH = 300


@dataclass(frozen=True)
class RejectionSummary:
    provider_type: str
    count: int
    last_at: datetime | None
    last_reason: str | None


@cache
def _client() -> redis.Redis:
    return redis.Redis.from_url(
        settings.CELERY_BROKER_URL, socket_connect_timeout=0.5, socket_timeout=0.5
    )


def _times_key(provider_type: str) -> str:
    return f"{KEY_PREFIX}:{provider_type}"


def _last_key(provider_type: str) -> str:
    return f"{KEY_PREFIX}:{provider_type}:last"


def record_rejection(provider_type: str, reason: str) -> None:
    now = time.time()
    try:
        pipe = _client().pipeline()
        times = _times_key(provider_type)
        pipe.zadd(times, {f"{now:.6f}:{uuid.uuid4().hex[:8]}": now})
        pipe.zremrangebyscore(times, 0, now - RETENTION_SECONDS)
        # Keep only the newest MAX_TRACKED: a flood costs a bounded set.
        pipe.zremrangebyrank(times, 0, -(MAX_TRACKED + 1))
        pipe.expire(times, RETENTION_SECONDS)
        pipe.set(
            _last_key(provider_type),
            json.dumps({"at": now, "reason": reason[:REASON_MAX_LENGTH]}),
            ex=RETENTION_SECONDS,
        )
        pipe.execute()
    except redis.RedisError as exc:
        logger.error("Could not count a rejected %s webhook in Redis: %s", provider_type, exc)


def rejection_summaries(
    provider_types: list[str], since: datetime
) -> list[RejectionSummary] | None:
    """Rejections per provider since ``since``, only those with any; None if Redis is down."""
    since_ts = since.timestamp()
    try:
        client = _client()
        pipe = client.pipeline()
        for provider_type in provider_types:
            pipe.zcount(_times_key(provider_type), since_ts, "+inf")
            pipe.get(_last_key(provider_type))
        results = pipe.execute()
    except redis.RedisError as exc:
        logger.error("Could not read rejected webhook counts from Redis: %s", exc)
        return None

    summaries = []
    for i, provider_type in enumerate(provider_types):
        count, last_raw = results[2 * i], results[2 * i + 1]
        if not count:
            continue
        last = json.loads(last_raw) if last_raw else {}
        summaries.append(
            RejectionSummary(
                provider_type=provider_type,
                count=int(count),
                last_at=(
                    datetime.fromtimestamp(last["at"], tz=timezone.utc) if "at" in last else None
                ),
                last_reason=last.get("reason"),
            )
        )
    return summaries
