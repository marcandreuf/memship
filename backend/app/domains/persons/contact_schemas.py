"""Contact schemas for person contact info."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.schema_types import NonBlank, refuse_null


class ContactResponse(BaseModel):
    id: int
    contact_type_id: int | None = None
    contact_type_name: str | None = None
    value: str
    label: str | None = None
    is_primary: bool = False

    model_config = {"from_attributes": True}


class ContactCreate(BaseModel):
    contact_type_id: int | None = None
    value: NonBlank(255)
    label: str | None = Field(default=None, max_length=100)
    is_primary: bool = False


class ContactUpdate(BaseModel):
    contact_type_id: int | None = None
    value: NonBlank(255) | None = None
    label: str | None = Field(default=None, max_length=100)
    is_primary: bool | None = None

    _not_null = field_validator("value")(refuse_null)
