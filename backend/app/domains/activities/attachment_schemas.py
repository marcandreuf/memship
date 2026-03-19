"""Activity attachment type and registration attachment schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


# --- ActivityAttachmentType ---

class ActivityAttachmentTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    allowed_extensions: list[str] = []
    max_file_size_mb: int = Field(default=5, ge=1, le=50)
    is_mandatory: bool = True
    display_order: int = 1


class ActivityAttachmentTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    allowed_extensions: list[str] | None = None
    max_file_size_mb: int | None = Field(default=None, ge=1, le=50)
    is_mandatory: bool | None = None
    display_order: int | None = None
    is_active: bool | None = None


class ActivityAttachmentTypeResponse(BaseModel):
    id: int
    activity_id: int
    name: str
    description: str | None = None
    allowed_extensions: list[str] = []
    max_file_size_mb: int
    is_mandatory: bool
    display_order: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- RegistrationAttachment ---

class RegistrationAttachmentResponse(BaseModel):
    id: int
    registration_id: int
    attachment_type_id: int | None = None
    file_name: str
    file_size: int | None = None
    mime_type: str | None = None
    uploaded_at: datetime | None = None

    model_config = {"from_attributes": True}
