"""Member and MembershipType schemas."""

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.domains.shared.enums import MemberStatus

Email = Annotated[str, StringConstraints(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)]


# --- MembershipType ---

class MembershipTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str | None = Field(default=None, max_length=2000)
    group_id: int | None = None
    base_price: float = Field(default=0, ge=0)
    billing_frequency: str = "annual"
    is_active: bool = True


class MembershipTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    group_id: int | None = None
    base_price: float | None = Field(default=None, ge=0)
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
    email: Email | None = None
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=20)
    national_id: str | None = Field(default=None, max_length=20)
    bank_iban: str | None = Field(default=None, max_length=34)
    bank_bic: str | None = Field(default=None, max_length=11)
    membership_type_id: int | None = None
    guardian_person_id: int | None = None
    internal_notes: str | None = Field(default=None, max_length=2000)

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, v: date | None) -> date | None:
        if v is not None and v > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return v


class MemberUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: Email | None = None
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=20)
    national_id: str | None = Field(default=None, max_length=20)
    bank_iban: str | None = Field(default=None, max_length=34)
    bank_bic: str | None = Field(default=None, max_length=11)
    membership_type_id: int | None = None
    guardian_person_id: int | None = None
    internal_notes: str | None = Field(default=None, max_length=2000)

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, v: date | None) -> date | None:
        if v is not None and v > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return v


class MemberStatusChange(BaseModel):
    status: MemberStatus
    reason: str | None = Field(default=None, max_length=2000)


class PersonResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    national_id: str | None = None
    photo_url: str | None = None
    bank_iban: str | None = None
    bank_bic: str | None = None

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
    description: str | None = Field(default=None, max_length=2000)
    is_billable: bool = True
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    icon: str | None = Field(default=None, max_length=50)


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    is_billable: bool | None = None
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    icon: str | None = Field(default=None, max_length=50)
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
