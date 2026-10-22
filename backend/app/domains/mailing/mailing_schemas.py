"""Schemas for the superadmin mailing-provider configuration screen.

Secrets are write-only: the GET view never returns a stored secret value, only
whether one is configured and its last four characters. On update, a secret
field left as ``None`` is unchanged; ``clear=True`` wipes it. Exactly one
provider is active at a time, selected by ``active_provider``.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# --- GET (masked) view ---


class MailSecretStatus(BaseModel):
    configured: bool
    last4: str | None = None


class MailHealthView(BaseModel):
    # Judged against the credentials resolved now: history recorded against
    # credentials that have since changed reads as "unverified".
    status: Literal["unverified", "ok", "failing"]
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    # An ``EmailFailure`` value; never the transport's own error text.
    last_failure: str | None = None


class MailResendView(BaseModel):
    from_email: str
    api_key: MailSecretStatus
    ready: bool
    health: MailHealthView


class MailSmtpView(BaseModel):
    # Any SMTP server; Gmail is a preset the screen fills in (#442).
    host: str
    port: int
    tls: bool
    user: str
    from_email: str
    password: MailSecretStatus
    ready: bool
    health: MailHealthView


class MailingConfigView(BaseModel):
    active_provider: Literal["resend", "smtp"] | None
    resend: MailResendView
    smtp: MailSmtpView
    secrets_encryption_available: bool
    # Per-field origin of the resolved value: "db" | "env" | "none", or
    # "default" for a typed setting nobody configured (SMTP port and TLS).
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


class MailSmtpUpdate(BaseModel):
    host: str | None = None
    # Port and TLS: None = unchanged; a value is stored as text like any field.
    port: int | None = Field(default=None, ge=1, le=65535)
    tls: bool | None = None
    user: str | None = None
    from_email: str | None = None
    password: MailSecretUpdate | None = None


class MailingConfigUpdate(BaseModel):
    # Presence is checked via model_fields_set so an explicit null (clear active
    # provider) is distinguishable from "not provided".
    active_provider: Literal["resend", "smtp"] | None = None
    resend: MailResendUpdate | None = None
    smtp: MailSmtpUpdate | None = None


# --- Test send ---


class MailingTestRequest(BaseModel):
    provider: Literal["resend", "smtp"]
    to: str | None = None


class MailingTestResult(BaseModel):
    ok: bool
    error: str | None = None

# --- Communications (which templates are switched on) ---


class CommunicationTemplateView(BaseModel):
    # ``key`` matches the email template and its ``_SUBJECTS`` entry; the UI
    # translates it rather than receiving a rendered label.
    key: str
    group: str
    tier: Literal["mandatory", "operational", "optional"]
    enabled: bool


class CommunicationsConfigView(BaseModel):
    templates: list[CommunicationTemplateView]


class CommunicationsConfigUpdate(BaseModel):
    # Sparse: only the keys present are changed. A mandatory key, or one absent
    # from the catalog, is rejected rather than silently ignored.
    templates: dict[str, bool]
