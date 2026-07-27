"""Resolve the active mail provider from the database, with env fallback.

The settings screen writes provider credentials into
``organization_settings.mailing_config`` (a JSONB column). For every field the
resolver prefers the DB value and falls back to the matching mail env var from
:mod:`app.core.config`, so a deployment already configured through ``.env`` keeps
sending untouched while new installs configure everything from the UI.

**Exactly one provider is active at a time.** A top-level ``active_provider``
(``"resend" | "gmail" | null``) selects the transport — there is no per-provider
enable flag, so no shape can turn two providers on at once. A provider is only
usable once its required fields resolve to non-empty values.

``active_provider`` resolution has three cases (mirrors ``sso_config`` adapted to
one-of-N):

* an explicit DB ``active_provider`` wins (gated on the provider being ready);
* a DB ``mailing_config`` node that exists but never set ``active_provider`` →
  **no active provider** (saving credentials does not auto-activate);
* **no DB node at all** → a pre-UI, env-only deployment: preserve the legacy
  ``send_email`` behaviour exactly — Resend if ``RESEND_API_KEY`` is set, else
  Gmail/SMTP if ``SMTP_HOST`` is set, else none — with no required-field gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.core.security import secrets_crypto
from app.domains.organizations.models import OrganizationSettings

# Gmail's SMTP endpoint is fixed for UI-configured accounts — the member only
# supplies their address and a Google app password, never a host/port. (A legacy
# env-only deployment keeps using whatever ``SMTP_HOST`` it already set.)
GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587
GMAIL_SMTP_TLS = True


@dataclass(frozen=True)
class FieldSpec:
    name: str
    env: str
    secret_default: bool


# Field → env-var mapping mirrors the existing mail settings one-to-one so the
# fallback is exact. ``secret_default`` marks which fields encrypt by default.
PROVIDER_FIELDS: dict[str, list[FieldSpec]] = {
    "resend": [
        FieldSpec("api_key", "RESEND_API_KEY", True),
        FieldSpec("from_email", "RESEND_FROM_EMAIL", False),
    ],
    "gmail": [
        FieldSpec("user", "SMTP_USER", False),
        FieldSpec("app_password", "SMTP_PASSWORD", True),
        FieldSpec("from_email", "SMTP_FROM", False),
    ],
}

# The fields that must resolve non-empty for a provider to be usable. ``from_email``
# is optional for both (Resend defaults to SMTP_FROM, Gmail to the account itself).
PROVIDER_REQUIRED = {
    "resend": ["api_key"],
    "gmail": ["user", "app_password"],
}


@dataclass
class ResolvedProvider:
    name: str
    values: dict[str, str]      # decrypted plaintext, only for non-empty fields
    sources: dict[str, str]     # field -> "db" | "env" | "none"
    secret_flags: dict[str, bool]

    @property
    def required(self) -> list[str]:
        return PROVIDER_REQUIRED[self.name]

    @property
    def ready(self) -> bool:
        """True when every required field resolves to a non-empty value."""
        return all(self.values.get(f) for f in self.required)

    def get(self, field_name: str) -> str:
        return self.values.get(field_name, "")

    def configured(self, field_name: str) -> bool:
        return bool(self.values.get(field_name))

    def last4(self, field_name: str) -> str | None:
        value = self.values.get(field_name, "")
        return value[-4:] if value else None

    def from_db(self, field_name: str) -> bool:
        return self.sources.get(field_name) == "db"


@dataclass
class ResolvedMailing:
    active: str | None            # "resend" | "gmail" | None, already readiness-gated
    resend: ResolvedProvider
    gmail: ResolvedProvider
    _env_only: bool = field(default=False, repr=False)

    def provider(self, name: str) -> ResolvedProvider | None:
        if name in ("resend", "gmail"):
            return getattr(self, name)
        return None

    def flat_sources(self) -> dict[str, str]:
        flat: dict[str, str] = {}
        for provider in (self.resend, self.gmail):
            for field_name, source in provider.sources.items():
                flat[f"{provider.name}.{field_name}"] = source
        return flat

    def gmail_smtp(self) -> tuple[str, int, bool]:
        """Effective SMTP host/port/TLS for the Gmail transport.

        UI-configured Gmail is pinned to Google's endpoint. A legacy env-only
        deployment keeps whatever ``SMTP_HOST`` it already had, so a non-Gmail
        SMTP server configured through ``.env`` still works unchanged.
        """
        if self.gmail.from_db("user") or self.gmail.from_db("app_password"):
            return GMAIL_SMTP_HOST, GMAIL_SMTP_PORT, GMAIL_SMTP_TLS
        return app_settings.SMTP_HOST, app_settings.SMTP_PORT, app_settings.SMTP_TLS


def _read_db_field(node: object, spec: FieldSpec) -> tuple[str, bool]:
    """Return ``(plaintext, secret_flag)`` for a stored field node.

    A missing/empty value yields ``""``. A secret value that cannot be decrypted
    (e.g. the key was rotated) is treated as empty so the flow degrades to the
    env fallback rather than raising during a send.
    """
    if not isinstance(node, dict):
        return "", spec.secret_default
    secret = bool(node.get("secret", spec.secret_default))
    raw = node.get("value") or ""
    if not raw:
        return "", secret
    if secret:
        try:
            return secrets_crypto.decrypt(raw), secret
        except (secrets_crypto.SecretDecryptError, secrets_crypto.SecretsKeyMissingError):
            return "", secret
    return raw, secret


def _resolve_provider(name: str, node: object) -> ResolvedProvider:
    values: dict[str, str] = {}
    sources: dict[str, str] = {}
    secret_flags: dict[str, bool] = {}

    for spec in PROVIDER_FIELDS[name]:
        field_node = node.get(spec.name) if isinstance(node, dict) else None
        db_value, secret = _read_db_field(field_node, spec)
        secret_flags[spec.name] = secret
        if db_value:
            values[spec.name] = db_value
            sources[spec.name] = "db"
            continue
        env_value = (getattr(app_settings, spec.env, "") or "").strip()
        if env_value:
            values[spec.name] = env_value
            sources[spec.name] = "env"
        else:
            sources[spec.name] = "none"

    return ResolvedProvider(
        name=name,
        values=values,
        sources=sources,
        secret_flags=secret_flags,
    )


def _resolve_active(raw: dict, resend: ResolvedProvider, gmail: ResolvedProvider) -> tuple[str | None, bool]:
    """Resolve which provider is active, and whether this is an env-only deployment.

    Returns ``(active, env_only)``.
    """
    providers = {"resend": resend, "gmail": gmail}

    if "active_provider" in raw:
        chosen = raw["active_provider"]
        if chosen in providers and providers[chosen].ready:
            return chosen, False
        return None, False

    if raw:
        # A DB node exists but active_provider was never set → nothing active.
        return None, False

    # No DB node at all → legacy env-only behaviour, matching the old send_email
    # transport priority exactly (Resend first, then SMTP), with no field gate.
    if app_settings.RESEND_API_KEY:
        return "resend", True
    if app_settings.SMTP_HOST:
        return "gmail", True
    return None, True


def resolve_mailing_config(db: Session) -> ResolvedMailing:
    row = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    raw = (row.mailing_config if row and row.mailing_config else {}) or {}

    resend = _resolve_provider("resend", raw.get("resend", {}))
    gmail = _resolve_provider("gmail", raw.get("gmail", {}))
    active, env_only = _resolve_active(raw, resend, gmail)

    return ResolvedMailing(active=active, resend=resend, gmail=gmail, _env_only=env_only)


def env_only_mailing_config() -> ResolvedMailing:
    """Resolve using only env vars, no DB access.

    Used as a safe fallback when the database is unreachable or the config row
    cannot be read, so a transient DB problem degrades mail to the legacy env
    behaviour rather than failing the send outright.
    """
    resend = _resolve_provider("resend", {})
    gmail = _resolve_provider("gmail", {})
    active, env_only = _resolve_active({}, resend, gmail)
    return ResolvedMailing(active=active, resend=resend, gmail=gmail, _env_only=env_only)


def mailing_enabled(db: Session) -> bool:
    """True when a usable mail transport resolves (DB or env)."""
    return resolve_mailing_config(db).active is not None


def build_field_node(value: str, secret: bool) -> dict:
    """Build a stored field node, encrypting the value when ``secret`` is set.

    The caller must ensure :func:`secrets_crypto.secrets_available` is true for a
    secret field; encryption raises otherwise.
    """
    stored = secrets_crypto.encrypt(value) if secret else value
    return {"value": stored, "secret": secret}