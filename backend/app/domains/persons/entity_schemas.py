"""Entity (non-person party) schemas.

An "entity" is the product word for a party whose kind is not ``person`` — a
company, public body, foundation or association the club holds a record of,
typically a donor. The club's own party is not an entity; the endpoints
exclude it.
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.schema_types import Email, NonBlank, refuse_null


class EntityResponse(BaseModel):
    id: int
    kind: str
    name: str
    legal_name: str | None = None
    national_id: str | None = None
    email: str | None = None
    created_at: datetime | None = None


class EntityCreate(BaseModel):
    kind: NonBlank(50)
    name: NonBlank(255)
    legal_name: str | None = Field(default=None, max_length=255)
    national_id: str | None = Field(default=None, max_length=50)
    email: Email | None = None


class EntityUpdate(BaseModel):
    kind: NonBlank(50) | None = None
    name: NonBlank(255) | None = None
    legal_name: str | None = Field(default=None, max_length=255)
    national_id: str | None = Field(default=None, max_length=50)
    email: Email | None = None

    _not_null = field_validator("kind", "name")(refuse_null)


class EntityAddressResponse(BaseModel):
    id: int
    address_line1: str
    address_line2: str | None = None
    city: str
    state_province: str | None = None
    postal_code: str | None = None
    country: str = "ES"

    model_config = {"from_attributes": True}


class EntityAddressUpdate(BaseModel):
    address_line1: NonBlank(255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: NonBlank(100)
    state_province: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str = Field(default="ES", max_length=3)


class PartySearchResult(BaseModel):
    id: int
    display_name: str
    kind: str
    national_id: str | None = None
