"""Which outbound email templates the organization has switched on.

The catalogue below is the single source of truth for every configurable email:
its key (matching the template file and the ``_SUBJECTS`` entry in
``app.core.email``), the group it is shown under in Settings, and its tier.

Three tiers, mirroring how much freedom the organization has:

- ``mandatory`` — the account-access mails. ``verification`` is the only way to
  activate an account, ``password_reset`` the only recovery path, and
  ``registration_existing_account`` the only thing an owner hears when someone
  tries to sign up as them — which is also the only reason ``/register`` can
  answer a known address the same way it answers an unknown one (#102). None can
  be switched off: ``is_enabled`` short-circuits to ``True`` and the API rejects
  an attempt to disable one. A member-level opt-out must not apply to these
  either (they rest on contract, not consent).
- ``operational`` — the member gained or lost something and has no other signal
  (a seat opened, the club cancelled their booking, a receipt was issued). The
  UI warns before switching one off.
- ``optional`` — confirmations whose state is visible in the portal anyway, plus
  the admin-facing summary and the broadcast channel.

Resolution is DB-with-default, and the default is **off**: a key absent from
``communications_config`` does not send. Nothing but the mandatory mails leaves
a fresh install until someone switches it on, so an organization opts
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
    TemplateSpec("registration_existing_account", "auth", "mandatory"),
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
    TemplateSpec("payment_confirmation", "billing", "operational"),
    TemplateSpec("billing_summary", "billing", "optional"),
    TemplateSpec("announcement", "broadcasts", "optional"),
)

BY_KEY: dict[str, TemplateSpec] = {spec.key: spec for spec in CATALOG}

MANDATORY: frozenset[str] = frozenset(
    spec.key for spec in CATALOG if spec.tier == "mandatory"
)

# ``mailing_test`` is deliberately absent: it is the settings screen's own
# credential check, not a member communication, and must send regardless. It is
# the *only* absence: an uncatalogued key has no switch to consult and so mails
# members on a fresh install that opted into nothing, which is how ``welcome``
# sat here unwired until #229 removed it. ``tests/unit/test_template_catalogue.py``
# holds the template files, this catalogue and ``_SUBJECTS`` to the same set.


def honours_member_opt_out(template_key: str) -> bool:
    """Whether a member's blanket "don't email me" silences this template.

    Only the ``optional`` tier. The other two are deliberate:

    - ``mandatory`` rests on contract, not consent — the docstring above says an
      opt-out must not reach it, and without ``verification`` or
      ``password_reset`` a member cannot hold an account at all.
    - ``operational`` carries ``receipt_delivery`` and ``payment_reminder``. A
      member who ticks one box must not thereby stop receiving their own
      invoices and the notices that precede a debt — a club may be obliged to
      send those, and will certainly want them sent.

    What is left is what the member loses nothing by losing: confirmations whose
    state is visible in the portal anyway, plus the broadcast channel. The UI
    copy beside the preference has to say that, or the toggle promises more than
    it does.

    A key with no catalogue entry has no tier, so it is never silenced here —
    the same reason ``always_sends`` lets it through.
    """
    spec = BY_KEY.get(template_key)
    return spec is not None and spec.tier == "optional"


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
