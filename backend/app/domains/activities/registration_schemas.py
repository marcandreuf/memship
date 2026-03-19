"""Registration schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    price_id: int
    modality_id: int | None = None
    registration_data: dict = {}
    member_notes: str | None = None


class CancelRegistrationRequest(BaseModel):
    reason: str | None = None


class AdminStatusChangeRequest(BaseModel):
    status: str = Field(pattern="^(confirmed|waitlist|cancelled|pending)$")
    admin_notes: str | None = None


class EligibilityResponse(BaseModel):
    eligible: bool
    reasons: list[str] = []


class RegistrationMemberInfo(BaseModel):
    id: int
    member_number: str | None = None
    first_name: str
    last_name: str
    email: str | None = None

    model_config = {"from_attributes": True}


class RegistrationActivityInfo(BaseModel):
    id: int
    name: str
    slug: str
    starts_at: datetime
    ends_at: datetime
    location: str | None = None

    model_config = {"from_attributes": True}


class RegistrationResponse(BaseModel):
    id: int
    activity_id: int
    member_id: int
    modality_id: int | None = None
    price_id: int | None = None
    status: str
    registration_data: dict = {}
    member_notes: str | None = None
    admin_notes: str | None = None
    cancelled_at: datetime | None = None
    cancelled_reason: str | None = None
    cancelled_by_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RegistrationDetailResponse(RegistrationResponse):
    """Registration with nested member and activity info for admin views."""
    member: RegistrationMemberInfo | None = None
    activity: RegistrationActivityInfo | None = None
