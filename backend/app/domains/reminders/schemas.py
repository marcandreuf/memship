"""Reminders schemas — admin notes & dated reminders."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.schema_types import NonBlankText, refuse_null


class ReminderCreate(BaseModel):
    content: NonBlankText(2000)
    # Omit or null → a plain note; a date → a dated reminder.
    due_date: date | None = None


class ReminderUpdate(BaseModel):
    content: NonBlankText(2000) | None = None
    due_date: date | None = None
    is_done: bool | None = None

    _not_null = field_validator("content")(refuse_null)


class ReminderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    due_date: date | None
    is_done: bool
    created_by: int | None
    created_at: datetime | None
    updated_at: datetime | None
