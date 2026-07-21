"""Schemas for the superadmin SSO configuration screen.

Secrets are write-only: the GET view never returns a stored secret value, only
whether one is configured and its last four characters. On update, a secret
field left as ``None`` is unchanged; ``clear=True`` wipes it.
"""

from pydantic import BaseModel


# --- GET (masked) view ---


class SsoSecretStatus(BaseModel):
    configured: bool
    last4: str | None = None


class SsoGoogleView(BaseModel):
    enabled: bool
    client_id: str
    client_secret: SsoSecretStatus
    ready: bool


class SsoAppleView(BaseModel):
    enabled: bool
    client_id: str
    team_id: str
    key_id: str
    private_key: SsoSecretStatus
    ready: bool


class SsoConfigView(BaseModel):
    google: SsoGoogleView
    apple: SsoAppleView
    # Read-only, from BACKEND_PUBLIC_URL — shown so the superadmin can paste the
    # redirect URIs into the Google / Apple consoles.
    backend_public_url: str
    redirect_uris: dict[str, str]
    secrets_encryption_available: bool
    # Per-field origin of the resolved value: "db" | "env" | "none".
    sources: dict[str, str]


# --- PUT (update) ---


class SsoSecretUpdate(BaseModel):
    # None = leave unchanged; a value = replace; clear=True = wipe. ``secret``
    # overrides whether the value is encrypted (defaults to True for these fields).
    value: str | None = None
    clear: bool = False
    secret: bool | None = None


class SsoGoogleUpdate(BaseModel):
    enabled: bool | None = None
    # Non-secret string fields: None = unchanged, "" = clear, value = set.
    client_id: str | None = None
    client_secret: SsoSecretUpdate | None = None


class SsoAppleUpdate(BaseModel):
    enabled: bool | None = None
    client_id: str | None = None
    team_id: str | None = None
    key_id: str | None = None
    private_key: SsoSecretUpdate | None = None


class SsoConfigUpdate(BaseModel):
    google: SsoGoogleUpdate | None = None
    apple: SsoAppleUpdate | None = None