"""Member and MembershipType schemas."""

from datetime import date, datetime

from pydantic import BaseModel, Field


# --- MembershipType ---

class MembershipTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str | None = None
    group_id: int | None = None
    base_price: float = 0
    billing_frequency: str = "annual"
    is_active: bool = True


class MembershipTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    group_id: int | None = None
    base_price: float | None = None
    billing_frequency: str | None = None
    is_active: bool | None = None


class MembershipTypeResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None = None
    group_id: int | None = None
    group_name: str | None = None
    base_price: float
    billing_frequency: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Member ---

class MemberCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    national_id: str | None = None
    membership_type_id: int | None = None
    guardian_person_id: int | None = None
    internal_notes: str | None = None


class MemberUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    national_id: str | None = None
    membership_type_id: int | None = None
    guardian_person_id: int | None = None
    internal_notes: str | None = None


class MemberStatusChange(BaseModel):
    status: str = Field(pattern=r"^(pending|active|suspended|cancelled|expired)$")
    reason: str | None = None


class PersonResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    national_id: str | None = None
    photo_url: str | None = None

    model_config = {"from_attributes": True}


class GuardianResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str | None = None

    model_config = {"from_attributes": True}


class MemberResponse(BaseModel):
    id: int
    person_id: int
    person: PersonResponse
    membership_type_id: int | None = None
    membership_type_name: str | None = None
    member_number: str | None = None
    status: str
    status_reason: str | None = None
    joined_at: date
    is_minor: bool = False
    guardian: GuardianResponse | None = None
    internal_notes: str | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Group ---

class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str | None = None
    is_billable: bool = True
    color: str | None = None
    icon: str | None = None


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    is_billable: bool | None = None
    color: str | None = None
    icon: str | None = None
    is_active: bool | None = None


class GroupResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None = None
    is_billable: bool
    display_order: int
    color: str | None = None
    icon: str | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
