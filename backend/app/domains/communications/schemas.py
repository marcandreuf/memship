"""Pydantic schemas for announcements and notifications."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.schema_types import NonBlank, NonBlankText, refuse_null

TARGET_PATTERN = "^(all|group|membership_type)$"


def validate_target(target_type: str, target_id: int | None) -> None:
    """Enforce the target_type / target_id relationship. Raises ValueError."""
    if target_type == "all":
        if target_id is not None:
            raise ValueError("target_id must be null when target_type is 'all'")
    elif target_id is None:
        raise ValueError("target_id is required when target_type is not 'all'")


class AnnouncementCreate(BaseModel):
    subject: NonBlank(200)
    body: NonBlankText()
    target_type: str = Field(..., pattern=TARGET_PATTERN)
    target_id: int | None = None

    @model_validator(mode="after")
    def _check_target(self) -> "AnnouncementCreate":
        validate_target(self.target_type, self.target_id)
        return self


class AnnouncementUpdate(BaseModel):
    # All optional — a partial edit of a draft. The merged target is validated
    # in the service (a partial body can't be cross-checked here).
    subject: NonBlank(200) | None = None
    body: NonBlankText() | None = None
    target_type: str | None = Field(None, pattern=TARGET_PATTERN)
    target_id: int | None = None

    _not_null = field_validator("subject", "body")(refuse_null)


class AnnouncementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject: str
    body: str
    target_type: str
    target_id: int | None = None
    status: str
    recipient_count: int | None = None
    sent_at: datetime | None = None
    created_by_user_id: int | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_type: str
    source_id: int
    title: str
    excerpt: str | None = None
    read_at: datetime | None = None
    created_at: datetime | None = None


class MarkReadRequest(BaseModel):
    ids: list[int] | None = None
    all: bool = False


class RecipientResponse(BaseModel):
    member_id: int
    name: str
    email: str | None = None
    # Could be emailed at send time: has an address, had not opted out.
    email_eligible: bool
    # Whether the fan-out delivered it. None on announcements sent before the
    # outcome was recorded (#228) — not known, as against known to have failed.
    emailed: bool | None = None
    in_app: bool
    seen_at: datetime | None = None  # in-app read timestamp; None for email-only


class RecipientStatsResponse(BaseModel):
    recipient_count: int
    # The audience that could be emailed, and the part of it that was. They
    # differ whenever a send fails — an absent transport, a bounce, a rejected
    # address — and reporting the first as the second is what #228 was.
    email_eligible_count: int
    emailed_count: int | None = None
    seen_count: int
    sent_by: str | None = None
