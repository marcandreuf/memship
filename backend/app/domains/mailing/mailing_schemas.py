"""Schemas for the superadmin mailing-provider configuration screen.

Secrets are write-only: the GET view never returns a stored secret value, only
whether one is configured and its last four characters. On update, a secret
field left as ``None`` is unchanged; ``clear=True`` wipes it. Exactly one
provider is active at a time, selected by ``active_provider``.
"""

from typing import Literal

from pydantic import BaseModel


# --- GET (masked) view ---


class MailSecretStatus(BaseModel):
    configured: bool
    last4: str | None = None


class MailResendView(BaseModel):
    from_email: str
    api_key: MailSecretStatus
    ready: bool


class MailGmailView(BaseModel):
    user: str
    from_email: str
    app_password: MailSecretStatus
    ready: bool


class MailingConfigView(BaseModel):
    active_provider: Literal["resend", "gmail"] | None
    resend: MailResendView
    gmail: MailGmailView
    secrets_encryption_available: bool
    # Per-field origin of the resolved value: "db" | "env" | "none".
    sources: dict[str, str]


# --- PUT (update) ---


class MailSecretUpdate(BaseModel):
    # None = leave unchanged; a value = replace; clear=True = wipe. ``secret``
    # overrides whether the value is encrypted (defaults to True for these fields).
    value: str | None = None
    clear: bool = False
    secret: bool | None = None


class MailResendUpdate(BaseModel):
    # Non-secret string fields: None = unchanged, "" = clear, value = set.
    from_email: str | None = None
    api_key: MailSecretUpdate | None = None


class MailGmailUpdate(BaseModel):
    user: str | None = None
    from_email: str | None = None
    app_password: MailSecretUpdate | None = None


class MailingConfigUpdate(BaseModel):
    # Presence is checked via model_fields_set so an explicit null (clear active
    # provider) is distinguishable from "not provided".
    active_provider: Literal["resend", "gmail"] | None = None
    resend: MailResendUpdate | None = None
    gmail: MailGmailUpdate | None = None


# --- Test send ---


class MailingTestRequest(BaseModel):
    provider: Literal["resend", "gmail"]
    to: str | None = None


class MailingTestResult(BaseModel):
    ok: bool
    error: str | None = None