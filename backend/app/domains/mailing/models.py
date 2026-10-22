"""Mail transport health — the outcome of the last send per provider (#338).

One row per provider, keyed by name. ``fingerprint`` identifies the credentials
the outcome was recorded against, so a replaced key or password reads as
unverified instead of inheriting the old one's history — whether it was changed
in the settings screen or in ``.env``.

Kept out of ``organization_settings.mailing_config`` on purpose: any key in that
node makes the resolver treat the install as UI-configured, which would switch
off an env-only deployment's provider the first time it sent a mail. It also
keeps a write per send off the single settings row that invoice numbering locks.
"""

from sqlalchemy import Column, DateTime, String, func

from app.db.base import Base


class MailTransportHealth(Base):
    __tablename__ = "mail_transport_health"

    provider = Column(String(20), primary_key=True)
    fingerprint = Column(String(64), nullable=False)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_at = Column(DateTime(timezone=True), nullable=True)
    # An ``EmailFailure`` value — coarse on purpose, never transport error text.
    last_failure = Column(String(40), nullable=True)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
