"""Custom profile field schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domains.shared.enums import (
    CustomFieldAdminAccess,
    CustomFieldMemberAccess,
    CustomFieldType,
)

# Locales the UI ships; label overrides outside this set are rejected so a typo
# doesn't silently produce a label nobody ever sees.
SUPPORTED_LOCALES = {"es", "ca", "en"}


class CustomFieldOption(BaseModel):
    value: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=100)


def _check_options(field_type: str | None, options: list[CustomFieldOption] | None):
    """`select` needs non-empty options with unique values; nothing else may have them."""
    if field_type == CustomFieldType.SELECT:
        if not options:
            raise ValueError("A select field requires at least one option")
        seen = [o.value for o in options]
        if len(seen) != len(set(seen)):
            raise ValueError("Option values must be unique")
    elif options:
        raise ValueError("Only a select field can define options")


def _check_labels(labels: dict[str, str] | None):
    if labels:
        unknown = set(labels) - SUPPORTED_LOCALES
        if unknown:
            raise ValueError(f"Unsupported locales: {', '.join(sorted(unknown))}")


class CustomFieldDefinitionCreate(BaseModel):
    # Immutable after creation — it is the API key values are addressed by.
    key: str = Field(min_length=1, max_length=50, pattern=r"^[a-z][a-z0-9_]*$")
    field_type: CustomFieldType
    label: str = Field(min_length=1, max_length=100)
    labels: dict[str, str] = Field(default_factory=dict)
    help_text: str | None = Field(default=None, max_length=255)
    options: list[CustomFieldOption] | None = None
    required: bool = False
    member_access: CustomFieldMemberAccess = CustomFieldMemberAccess.READ
    admin_access: CustomFieldAdminAccess = CustomFieldAdminAccess.WRITE
    sort_order: int = Field(default=0, ge=0)
    active: bool = True

    @model_validator(mode="after")
    def validate_shape(self):
        _check_options(self.field_type, self.options)
        _check_labels(self.labels)
        return self


class CustomFieldDefinitionUpdate(BaseModel):
    """`key` and `field_type` are absent by design — both are immutable."""

    label: str | None = Field(default=None, min_length=1, max_length=100)
    labels: dict[str, str] | None = None
    help_text: str | None = Field(default=None, max_length=255)
    options: list[CustomFieldOption] | None = None
    required: bool | None = None
    member_access: CustomFieldMemberAccess | None = None
    admin_access: CustomFieldAdminAccess | None = None
    sort_order: int | None = Field(default=None, ge=0)
    active: bool | None = None

    @model_validator(mode="after")
    def validate_shape(self):
        _check_labels(self.labels)
        return self


class CustomFieldDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    field_type: CustomFieldType
    label: str
    labels: dict[str, str]
    help_text: str | None
    options: list[CustomFieldOption] | None
    required: bool
    member_access: CustomFieldMemberAccess
    admin_access: CustomFieldAdminAccess
    sort_order: int
    active: bool
    created_at: datetime | None
    updated_at: datetime | None
    # Resolved for the requesting user, so the UI never has to replay the
    # access rules itself.
    writable: bool = True
