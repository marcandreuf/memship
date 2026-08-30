"""Which outbound email templates the organization has switched on.

The catalogue below is the single source of truth for every configurable email:
its key (matching the template file and the ``_SUBJECTS`` entry in
``app.core.email``), the group it is shown under in Settings, and its tier.

Three tiers, mirroring how much freedom the organization has:

- ``mandatory`` — the account-access mails. ``verification`` is the only way to
  activate an account and ``password_reset`` the only recovery path, so neither
  can be switched off: ``is_enabled`` short-circuits to ``True`` and the API
  rejects an attempt to disable one. A member-level opt-out must not apply to
  these either (they rest on contract, not consent).
- ``operational`` — the member gained or lost something and has no other signal
  (a seat opened, the club cancelled their booking, a receipt was issued). The
  UI warns before switching one off.
- ``optional`` — confirmations whose state is visible in the portal anyway, plus
  the admin-facing summary and the broadcast channel.

Resolution is DB-with-default, and the default is **off**: a key absent from
``communications_config`` does not send. Nothing but the two mandatory mails
leaves a fresh install until someone switches it on, so an organization opts
into each channel rather than discovering it after members have been mailed. A
key with no catalogue entry is not configurable and always sends.
"""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.domains.organizations.models import OrganizationSettings

Tier = Literal["mandatory", "operational", "optional"]


@dataclass(frozen=True)
class TemplateSpec:
    key: str
    group: str
    tier: Tier


# Ordered — the settings screen renders it in this order, grouped by ``group``.
CATALOG: tuple[TemplateSpec, ...] = (
    TemplateSpec("verification", "auth", "mandatory"),
    TemplateSpec("password_reset", "auth", "mandatory"),
    TemplateSpec("registration_approved", "members", "operational"),
    TemplateSpec("registration_rejected", "members", "optional"),
    TemplateSpec("registration_confirmed", "activities", "optional"),
    TemplateSpec("registration_waitlisted", "activities", "optional"),
    TemplateSpec("registration_cancelled", "activities", "optional"),
    TemplateSpec("waitlist_promoted", "activities", "operational"),
    TemplateSpec("booking_confirmation", "bookings", "optional"),
    TemplateSpec("booking_waitlisted", "bookings", "optional"),
    TemplateSpec("booking_promoted", "bookings", "operational"),
    TemplateSpec("booking_cancelled", "bookings", "operational"),
    TemplateSpec("receipt_delivery", "billing", "operational"),
    TemplateSpec("payment_reminder", "billing", "operational"),
    TemplateSpec("billing_summary", "billing", "optional"),
    TemplateSpec("announcement", "broadcasts", "optional"),
)

BY_KEY: dict[str, TemplateSpec] = {spec.key: spec for spec in CATALOG}

MANDATORY: frozenset[str] = frozenset(
    spec.key for spec in CATALOG if spec.tier == "mandatory"
)

# ``mailing_test`` is deliberately absent: it is the settings screen's own
# credential check, not a member communication, and must send regardless.


def always_sends(template_key: str) -> bool:
    """Whether ``template_key`` bypasses the configuration entirely.

    True for the mandatory account-access mails and for any key with no
    catalogue entry — neither has a switch to consult. Answerable without a
    session, so a caller can settle these before touching the database.
    """
    return template_key in MANDATORY or template_key not in BY_KEY


def is_enabled(db: Session, template_key: str) -> bool:
    """Whether ``template_key`` may be sent, per the stored configuration.

    Templates that ``always_sends`` covers need no lookup. Everything else
    sends only once the organization has explicitly turned it on.
    """
    if always_sends(template_key):
        return True

    row = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    config = (row.communications_config if row and row.communications_config else {}) or {}
    node = (config.get("templates") or {}).get(template_key) or {}
    return node.get("enabled", False) is True


def enabled_map(db: Session) -> dict[str, bool]:
    """Every catalogue key with its resolved state, for the settings view."""
    row = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    config = (row.communications_config if row and row.communications_config else {}) or {}
    templates = config.get("templates") or {}
    return {
        spec.key: (
            True
            if spec.tier == "mandatory"
            else (templates.get(spec.key) or {}).get("enabled", False) is True
        )
        for spec in CATALOG
    }
