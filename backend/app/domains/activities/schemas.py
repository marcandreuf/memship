"""Activity, modality, and price schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


# --- ActivityModality ---


class ActivityModalityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    max_participants: int | None = None
    registration_deadline: datetime | None = None
    display_order: int = 1


class ActivityModalityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    max_participants: int | None = None
    registration_deadline: datetime | None = None
    display_order: int | None = None


class ActivityModalityResponse(BaseModel):
    id: int
    activity_id: int
    name: str
    description: str | None = None
    max_participants: int | None = None
    current_participants: int = 0
    registration_deadline: datetime | None = None
    display_order: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- ActivityPrice ---


class ActivityPriceCreate(BaseModel):
    name: str = Field(default="General Price", min_length=1, max_length=255)
    description: str | None = None
    amount: float = Field(ge=0)
    modality_id: int | None = None
    display_order: int = 1
    is_optional: bool = False
    is_default: bool = False
    is_visible: bool = True
    max_registrations: int | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class ActivityPriceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    amount: float | None = Field(default=None, ge=0)
    modality_id: int | None = None
    display_order: int | None = None
    is_optional: bool | None = None
    is_default: bool | None = None
    is_visible: bool | None = None
    max_registrations: int | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class ActivityPriceResponse(BaseModel):
    id: int
    activity_id: int
    modality_id: int | None = None
    name: str
    description: str | None = None
    amount: float
    display_order: int
    is_optional: bool
    is_default: bool
    is_visible: bool
    max_registrations: int | None = None
    current_registrations: int = 0
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Activity ---


class ActivityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    short_description: str | None = Field(default=None, max_length=500)
    starts_at: datetime
    ends_at: datetime
    location: str | None = Field(default=None, max_length=255)
    location_details: str | None = None
    location_url: str | None = Field(default=None, max_length=500)
    registration_starts_at: datetime
    registration_ends_at: datetime
    min_participants: int = Field(default=0, ge=0)
    max_participants: int = Field(ge=1)
    min_age: int | None = None
    max_age: int | None = None
    allowed_membership_types: list[int] | None = None
    tax_rate: float = Field(default=0, ge=0, le=100)
    features: dict = {}
    registration_fields_schema: list = []
    requirements: str | None = None
    what_to_bring: str | None = None
    cancellation_policy: str | None = None
    allow_self_cancellation: bool = False
    self_cancellation_deadline_hours: int | None = None


class ActivityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    short_description: str | None = Field(default=None, max_length=500)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    location: str | None = Field(default=None, max_length=255)
    location_details: str | None = None
    location_url: str | None = Field(default=None, max_length=500)
    registration_starts_at: datetime | None = None
    registration_ends_at: datetime | None = None
    min_participants: int | None = Field(default=None, ge=0)
    max_participants: int | None = Field(default=None, ge=1)
    min_age: int | None = None
    max_age: int | None = None
    allowed_membership_types: list[int] | None = None
    tax_rate: float | None = Field(default=None, ge=0, le=100)
    features: dict | None = None
    registration_fields_schema: list | None = None
    requirements: str | None = None
    what_to_bring: str | None = None
    cancellation_policy: str | None = None
    allow_self_cancellation: bool | None = None
    self_cancellation_deadline_hours: int | None = None
    is_featured: bool | None = None


class ActivityResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None = None
    short_description: str | None = None
    starts_at: datetime
    ends_at: datetime
    location: str | None = None
    location_details: str | None = None
    location_url: str | None = None
    registration_starts_at: datetime
    registration_ends_at: datetime
    min_participants: int
    max_participants: int
    current_participants: int
    waitlist_count: int
    available_spots: int = 0
    is_registration_open: bool = False
    min_age: int | None = None
    max_age: int | None = None
    allowed_membership_types: list[int] | None = None
    status: str
    tax_rate: float
    image_url: str | None = None
    thumbnail_url: str | None = None
    features: dict = {}
    registration_fields_schema: list = []
    requirements: str | None = None
    what_to_bring: str | None = None
    cancellation_policy: str | None = None
    allow_self_cancellation: bool
    self_cancellation_deadline_hours: int | None = None
    is_active: bool
    is_featured: bool
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime
    modalities: list[ActivityModalityResponse] = []
    prices: list[ActivityPriceResponse] = []

    model_config = {"from_attributes": True}


class ActivityListResponse(BaseModel):
    id: int
    name: str
    slug: str
    short_description: str | None = None
    starts_at: datetime
    ends_at: datetime
    location: str | None = None
    max_participants: int
    current_participants: int
    available_spots: int = 0
    is_registration_open: bool = False
    status: str
    is_featured: bool
    created_at: datetime

    model_config = {"from_attributes": True}
