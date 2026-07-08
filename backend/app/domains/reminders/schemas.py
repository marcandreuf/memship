"""Reminders schemas — admin notes & dated reminders."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ReminderCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    # Omit or null → a plain note; a date → a dated reminder.
    due_date: date | None = None


class ReminderUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=2000)
    due_date: date | None = None
    is_done: bool | None = None


class ReminderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    due_date: date | None
    is_done: bool
    created_by: int | None
    created_at: datetime | None
    updated_at: datetime | None
