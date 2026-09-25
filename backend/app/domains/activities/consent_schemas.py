"""Activity consent and registration consent schemas."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.schema_types import NonBlank, NonBlankText, refuse_null


# --- ActivityConsent ---

class ActivityConsentCreate(BaseModel):
    title: NonBlank(255)
    content: NonBlankText(10000)
    is_mandatory: bool = True
    display_order: int = Field(default=1, ge=0)


class ActivityConsentUpdate(BaseModel):
    title: NonBlank(255) | None = None
    content: NonBlankText(10000) | None = None
    is_mandatory: bool | None = None
    display_order: int | None = None
    is_active: bool | None = None

    _not_null = field_validator("title", "content")(refuse_null)


class ActivityConsentResponse(BaseModel):
    id: int
    activity_id: int
    title: str
    content: str
    is_mandatory: bool
    display_order: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- RegistrationConsent ---

class ConsentAcceptance(BaseModel):
    """Used during registration to accept/decline a consent."""
    activity_consent_id: int
    accepted: bool = True


class RegistrationConsentResponse(BaseModel):
    id: int
    registration_id: int
    activity_consent_id: int
    accepted: bool
    accepted_at: datetime | None = None
    consent_title: str | None = None

    model_config = {"from_attributes": True}
