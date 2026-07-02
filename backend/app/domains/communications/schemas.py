"""Pydantic schemas for announcements and notifications."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

TARGET_PATTERN = "^(all|group|membership_type)$"


def validate_target(target_type: str, target_id: int | None) -> None:
    """Enforce the target_type / target_id relationship. Raises ValueError."""
    if target_type == "all":
        if target_id is not None:
            raise ValueError("target_id must be null when target_type is 'all'")
    elif target_id is None:
        raise ValueError("target_id is required when target_type is not 'all'")


class AnnouncementCreate(BaseModel):
    subject: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1)
    target_type: str = Field(..., pattern=TARGET_PATTERN)
    target_id: int | None = None

    @model_validator(mode="after")
    def _check_target(self) -> "AnnouncementCreate":
        validate_target(self.target_type, self.target_id)
        return self


class AnnouncementUpdate(BaseModel):
    # All optional — a partial edit of a draft. The merged target is validated
    # in the service (a partial body can't be cross-checked here).
    subject: str | None = Field(None, min_length=1, max_length=200)
    body: str | None = Field(None, min_length=1)
    target_type: str | None = Field(None, pattern=TARGET_PATTERN)
    target_id: int | None = None


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
    emailed: bool
    in_app: bool
    seen_at: datetime | None = None  # in-app read timestamp; None for email-only


class RecipientStatsResponse(BaseModel):
    recipient_count: int
    emailed_count: int
    seen_count: int
    sent_by: str | None = None
