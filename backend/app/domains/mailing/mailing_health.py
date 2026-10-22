"""Whether each mail provider's current credentials are known to work (#338).

Every send through a provider — a real mail or the settings screen's test —
records its outcome against a fingerprint of the credentials it used. Reading
it back compares that fingerprint with the credentials resolved now, so the
history follows the credential, not the provider name:

* ``unverified`` — nothing has gone through these credentials yet;
* ``ok`` — the most recent send through them was accepted;
* ``failing`` — the most recent send through them was refused.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import case, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.domains.mailing.mailing_config import PROVIDER_FIELDS, ResolvedMailing
from app.domains.mailing.models import MailTransportHealth

HealthStatus = Literal["unverified", "ok", "failing"]


@dataclass(frozen=True)
class ProviderHealth:
    status: HealthStatus
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_failure: str | None = None


UNVERIFIED = ProviderHealth(status="unverified")


def credential_fingerprint(resolved: ResolvedMailing, provider: str) -> str:
    """Keyed hash of everything that decides where a provider's mail goes.

    Keyed with ``SECRET_KEY`` so the stored value cannot be used to confirm a
    guessed credential. For SMTP the host, port and TLS flag are fields like the
    rest: the same account against another server is an unproven transport.
    """
    p = resolved.provider(provider)
    parts = [provider] + [f"{spec.name}={p.get(spec.name)}" for spec in PROVIDER_FIELDS[provider]]
    return hmac.new(
        app_settings.SECRET_KEY.encode(), "\x1f".join(parts).encode(), hashlib.sha256
    ).hexdigest()


def record_outcome(
    db: Session, resolved: ResolvedMailing, provider: str, failure: str | None
) -> None:
    """Record one send's outcome; ``failure`` is ``None`` for a delivered mail.

    A single upsert, so concurrent senders cannot interleave a read and a write.
    When the fingerprint has changed, the other side's history belonged to the
    previous credentials and is dropped. The caller commits.
    """
    now = datetime.now(timezone.utc)
    fingerprint = credential_fingerprint(resolved, provider)
    table = MailTransportHealth.__table__
    stmt = insert(table).values(
        provider=provider,
        fingerprint=fingerprint,
        last_success_at=now if failure is None else None,
        last_failure_at=now if failure is not None else None,
        last_failure=failure,
    )
    same = table.c.fingerprint == stmt.excluded.fingerprint
    if failure is None:
        updates = {
            "last_success_at": now,
            "last_failure_at": case((same, table.c.last_failure_at), else_=None),
            "last_failure": case((same, table.c.last_failure), else_=None),
        }
    else:
        updates = {
            "last_failure_at": now,
            "last_failure": failure,
            "last_success_at": case((same, table.c.last_success_at), else_=None),
        }
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=[table.c.provider],
            set_={"fingerprint": fingerprint, "updated_at": func.now(), **updates},
        )
    )


def _health_of(row: MailTransportHealth | None, fingerprint: str) -> ProviderHealth:
    if row is None or row.fingerprint != fingerprint:
        return UNVERIFIED
    if row.last_failure_at and (
        row.last_success_at is None or row.last_failure_at > row.last_success_at
    ):
        status: HealthStatus = "failing"
    elif row.last_success_at:
        status = "ok"
    else:
        return UNVERIFIED
    return ProviderHealth(
        status=status,
        last_success_at=row.last_success_at,
        last_failure_at=row.last_failure_at,
        last_failure=row.last_failure,
    )


def provider_health(db: Session, resolved: ResolvedMailing) -> dict[str, ProviderHealth]:
    """Health of every provider, judged against its currently resolved credentials."""
    rows = {row.provider: row for row in db.query(MailTransportHealth).all()}
    return {
        name: _health_of(rows.get(name), credential_fingerprint(resolved, name))
        for name in PROVIDER_FIELDS
    }
