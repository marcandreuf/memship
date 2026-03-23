"""Organization settings schemas."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

Email = Annotated[str, StringConstraints(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)]


class OrganizationSettingsResponse(BaseModel):
    id: int
    name: str
    legal_name: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    logo_url: str | None = None
    tax_id: str | None = None
    locale: str
    timezone: str
    currency: str
    date_format: str
    brand_color: str | None = None
    features: dict = {}
    custom_settings: dict = {}
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrganizationSettingsUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    email: Email | None = None
    phone: str | None = Field(default=None, max_length=50)
    website: str | None = Field(default=None, max_length=500)
    logo_url: str | None = Field(default=None, max_length=500)
    tax_id: str | None = Field(default=None, max_length=50)
    locale: str | None = Field(default=None, pattern=r"^(es|ca|en)$")
    timezone: str | None = Field(default=None, max_length=50)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    date_format: str | None = Field(default=None, max_length=20)
    brand_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    features: dict | None = None
    custom_settings: dict | None = None
