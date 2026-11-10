"""Schemas for the superadmin mailing-provider configuration screen.

Secrets are write-only: the GET view never returns a stored secret value, only
whether one is configured and its last four characters. On update, a secret
field left as ``None`` is unchanged; ``clear=True`` wipes it. Exactly one
provider is active at a time, selected by ``active_provider``.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


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
    security: Literal["off", "starttls", "ssl"]
    # Derived from ``security``, for clients written against the boolean. Either
    # encrypted mode reads as true: this field's question was ever only "is this
    # encrypted", so reporting implicit TLS as false would read as encryption
    # being off (#577).
    tls: bool = Field(
        deprecated="Replaced by security; removed in the next major.",
    )
    user: str
    from_email: str
    password: MailSecretStatus
    ready: bool
    health: MailHealthView


class MailSendpulseView(BaseModel):
    # Configured from this screen only: SendPulse postdates it, so there is no
    # .env path to be compatible with (#576).
    from_email: str
    from_name: str
    api_key: MailSecretStatus
    ready: bool
    health: MailHealthView


class MailingConfigView(BaseModel):
    active_provider: Literal["resend", "smtp", "sendpulse"] | None
    resend: MailResendView
    smtp: MailSmtpView
    sendpulse: MailSendpulseView
    secrets_encryption_available: bool
    # Per-field origin of the resolved value: "db" | "env" | "none", or
    # "default" for a typed setting nobody configured (SMTP port and security).
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
    # Port and security: None = unchanged; a value is stored as text like any
    # field. An unrecognised security mode is refused by the Literal rather than
    # coerced, which is the defect #577 reports.
    port: int | None = Field(default=None, ge=1, le=65535)
    security: Literal["off", "starttls", "ssl"] | None = None
    tls: bool | None = Field(
        default=None,
        deprecated="Replaced by security; removed in the next major.",
    )
    user: str | None = None
    from_email: str | None = None
    password: MailSecretUpdate | None = None

    @model_validator(mode="after")
    def _tls_means_security(self) -> "MailSmtpUpdate":
        """Fold the deprecated boolean into ``security``.

        ``security`` wins when a client sends both, so a caller that has migrated
        is never overridden by a boolean it also still sends. Translating here
        rather than in the endpoint keeps the alias beside the field it replaces,
        and leaves exactly one name for the rest of the write path to store.
        """
        # Read through ``__dict__``: pydantic implements ``deprecated=`` as a
        # warning on attribute access, and this translation is the one read that
        # is not a caller using the old name.
        tls = self.__dict__.get("tls")
        if tls is not None and self.security is None:
            self.security = "starttls" if tls else "off"
        return self


class MailSendpulseUpdate(BaseModel):
    from_email: str | None = None
    from_name: str | None = None
    api_key: MailSecretUpdate | None = None


class MailingConfigUpdate(BaseModel):
    # Presence is checked via model_fields_set so an explicit null (clear active
    # provider) is distinguishable from "not provided".
    active_provider: Literal["resend", "smtp", "sendpulse"] | None = None
    resend: MailResendUpdate | None = None
    smtp: MailSmtpUpdate | None = None
    sendpulse: MailSendpulseUpdate | None = None


# --- Test send ---


class MailingTestRequest(BaseModel):
    provider: Literal["resend", "smtp", "sendpulse"]
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
