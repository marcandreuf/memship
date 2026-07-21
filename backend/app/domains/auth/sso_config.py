"""Resolve SSO provider configuration from the database, with env fallback.

The settings screen writes provider credentials into
``organization_settings.sso_config`` (a JSONB column). For every field the
resolver prefers the DB value and falls back to the matching env var from
:mod:`app.core.config`, so a deployment already configured through ``.env``
keeps working untouched while new installs configure everything from the UI.

A provider is only *ready* — offered to members and usable for a login — when it
is enabled **and** all of its required fields resolve to a non-empty value.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.core.security import secrets_crypto
from app.domains.organizations.models import OrganizationSettings


@dataclass(frozen=True)
class FieldSpec:
    name: str
    env: str
    secret_default: bool


# Field → env-var mapping mirrors the v1.2.0 env vars one-to-one so the fallback
# is exact. ``secret_default`` marks which fields encrypt by default.
PROVIDER_FIELDS: dict[str, list[FieldSpec]] = {
    "google": [
        FieldSpec("client_id", "GOOGLE_CLIENT_ID", False),
        FieldSpec("client_secret", "GOOGLE_CLIENT_SECRET", True),
    ],
    "apple": [
        FieldSpec("client_id", "APPLE_CLIENT_ID", False),
        FieldSpec("team_id", "APPLE_TEAM_ID", False),
        FieldSpec("key_id", "APPLE_KEY_ID", False),
        FieldSpec("private_key", "APPLE_PRIVATE_KEY", True),
    ],
}

# Every field a provider declares is required for it to be usable.
PROVIDER_REQUIRED = {name: [f.name for f in fields] for name, fields in PROVIDER_FIELDS.items()}


@dataclass
class ResolvedProvider:
    name: str
    enabled: bool
    values: dict[str, str]      # decrypted plaintext, only for non-empty fields
    sources: dict[str, str]     # field -> "db" | "env" | "none"
    secret_flags: dict[str, bool]

    @property
    def required(self) -> list[str]:
        return PROVIDER_REQUIRED[self.name]

    @property
    def ready(self) -> bool:
        return self.enabled and all(self.values.get(f) for f in self.required)

    def get(self, field: str) -> str:
        return self.values.get(field, "")

    def configured(self, field: str) -> bool:
        return bool(self.values.get(field))

    def last4(self, field: str) -> str | None:
        value = self.values.get(field, "")
        return value[-4:] if value else None


@dataclass
class ResolvedSso:
    google: ResolvedProvider
    apple: ResolvedProvider

    def provider(self, name: str) -> ResolvedProvider | None:
        return getattr(self, name, None)

    def flat_sources(self) -> dict[str, str]:
        flat: dict[str, str] = {}
        for provider in (self.google, self.apple):
            for field, source in provider.sources.items():
                flat[f"{provider.name}.{field}"] = source
        return flat


def _read_db_field(node: object, spec: FieldSpec) -> tuple[str, bool]:
    """Return ``(plaintext, secret_flag)`` for a stored field node.

    A missing/empty value yields ``""``. A secret value that cannot be decrypted
    (e.g. the key was rotated) is treated as empty so the flow degrades to the
    env fallback rather than raising during a login.
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

    # `enabled` sourcing:
    #  - explicit DB flag wins (the settings screen always writes one);
    #  - a DB node that exists but never set the flag is treated as off, so
    #    saving credentials does not auto-enable a provider;
    #  - no DB node at all is a pre-UI (env-only) deployment: keep v1.2.0
    #    behaviour and enable implicitly once every required field resolves.
    if isinstance(node, dict) and "enabled" in node:
        enabled = bool(node["enabled"])
    elif isinstance(node, dict) and node:
        enabled = False
    else:
        enabled = all(values.get(f) for f in PROVIDER_REQUIRED[name])

    return ResolvedProvider(
        name=name,
        enabled=enabled,
        values=values,
        sources=sources,
        secret_flags=secret_flags,
    )


def resolve_sso_config(db: Session) -> ResolvedSso:
    row = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    raw = (row.sso_config if row and row.sso_config else {}) or {}
    return ResolvedSso(
        google=_resolve_provider("google", raw.get("google", {})),
        apple=_resolve_provider("apple", raw.get("apple", {})),
    )


def build_field_node(value: str, secret: bool) -> dict:
    """Build a stored field node, encrypting the value when ``secret`` is set.

    The caller must ensure :func:`secrets_crypto.secrets_available` is true for a
    secret field; encryption raises otherwise.
    """
    stored = secrets_crypto.encrypt(value) if secret else value
    return {"value": stored, "secret": secret}