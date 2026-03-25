"""Organization address schemas."""

from pydantic import BaseModel, Field


class OrganizationAddressResponse(BaseModel):
    id: int
    address_line1: str
    address_line2: str | None = None
    city: str
    state_province: str | None = None
    postal_code: str | None = None
    country: str = "ES"

    model_config = {"from_attributes": True}


class OrganizationAddressUpdate(BaseModel):
    address_line1: str = Field(min_length=1, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str = Field(min_length=1, max_length=100)
    state_province: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str = Field(default="ES", max_length=3)
