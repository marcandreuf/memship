"""Simple Bookings schemas."""

from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.pagination import PageMeta


# --- Spaces ---------------------------------------------------------------


class SpaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    space_type: str | None = Field(default=None, max_length=50)
    description: str | None = None
    open_time: time
    close_time: time
    is_active: bool = True

    @model_validator(mode="after")
    def _hours(self):
        if self.close_time <= self.open_time:
            raise ValueError("close_time must be after open_time")
        return self


class SpaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    space_type: str | None = Field(default=None, max_length=50)
    description: str | None = None
    open_time: time | None = None
    close_time: time | None = None
    is_active: bool | None = None


class SpaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    space_type: str | None
    description: str | None
    open_time: time
    close_time: time
    is_active: bool
    created_at: datetime | None
    updated_at: datetime | None


# --- Slots ----------------------------------------------------------------


class SlotRepeat(BaseModel):
    """Materialized repeat rule: selected weekdays × every N weeks × count weeks."""

    weekdays: list[int] = Field(default_factory=list)
    interval_weeks: int = Field(default=1, ge=1, le=12)
    count: int = Field(default=1, ge=1, le=52)

    @model_validator(mode="after")
    def _weekdays(self):
        if any(d < 0 or d > 6 for d in self.weekdays):
            raise ValueError("weekdays must be 0 (Mon) to 6 (Sun)")
        return self


class SpaceSlotCreate(BaseModel):
    slot_date: date
    start_time: time | None = None
    end_time: time | None = None
    # all_day expands to the space's opening hours in the service.
    all_day: bool = False
    capacity: int = Field(default=1, ge=1)
    is_active: bool = True
    repeat: SlotRepeat | None = None

    @model_validator(mode="after")
    def _times(self):
        if not self.all_day:
            if self.start_time is None or self.end_time is None:
                raise ValueError("start_time and end_time are required unless all_day")
            if self.end_time <= self.start_time:
                raise ValueError("end_time must be after start_time")
        return self


class SpaceSlotUpdate(BaseModel):
    slot_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    all_day: bool = False
    capacity: int | None = Field(default=None, ge=1)
    is_active: bool | None = None


class SpaceSlotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    space_id: int
    slot_date: date
    start_time: time
    end_time: time
    capacity: int
    series_id: UUID | None
    is_active: bool
    # Slots in this slot's series dated today-or-later than it (itself included);
    # the edit dialog asks "this or upcoming" only when > 1.
    series_size_upcoming: int = 1


# --- Bookings -------------------------------------------------------------


class BookingCreate(BaseModel):
    space_slot_id: int


class BookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    space_slot_id: int
    member_id: int
    status: str
    created_at: datetime | None


class MyBookingRead(BaseModel):
    """A member's own booking, denormalized for the My Bookings list."""

    id: int
    space_slot_id: int
    space_id: int
    space_name: str
    slot_date: date
    start_time: time
    end_time: time
    status: str
    capacity: int
    booked_count: int
    waitlist_position: int | None = None


class AdminBookingRead(BaseModel):
    id: int
    space_slot_id: int
    member_id: int
    member_name: str
    slot_date: date
    start_time: time
    end_time: time
    status: str


class AdminBookingPage(BaseModel):
    meta: PageMeta
    items: list[AdminBookingRead]


# --- Availability ---------------------------------------------------------


class AvailabilityCell(BaseModel):
    space_slot_id: int
    date: date
    weekday: int
    start_time: time
    end_time: time
    capacity: int
    booked_count: int
    waitlist_count: int
    # none | booked | waitlisted
    my_status: str
    # open | full | past | out_of_window
    cell_state: str


class WeekAvailability(BaseModel):
    space_id: int
    week_start: date
    cells: list[AvailabilityCell]
