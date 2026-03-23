"""Activity consent and registration consent schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


# --- ActivityConsent ---

class ActivityConsentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=10000)
    is_mandatory: bool = True
    display_order: int = Field(default=1, ge=0)


class ActivityConsentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None, min_length=1, max_length=10000)
    is_mandatory: bool | None = None
    display_order: int | None = None
    is_active: bool | None = None


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
