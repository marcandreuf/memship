"""Simple Bookings schemas."""

from datetime import date, datetime, time

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


class SpaceSlotCreate(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    capacity: int = Field(default=1, ge=1)
    is_active: bool = True

    @model_validator(mode="after")
    def _times(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class SpaceSlotUpdate(BaseModel):
    weekday: int | None = Field(default=None, ge=0, le=6)
    start_time: time | None = None
    end_time: time | None = None
    capacity: int | None = Field(default=None, ge=1)
    is_active: bool | None = None


class SpaceSlotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    space_id: int
    weekday: int
    start_time: time
    end_time: time
    capacity: int
    is_active: bool


# --- Bookings -------------------------------------------------------------


class BookingCreate(BaseModel):
    space_slot_id: int
    booking_date: date


class BookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    space_slot_id: int
    member_id: int
    booking_date: date
    status: str
    created_at: datetime | None


class MyBookingRead(BaseModel):
    """A member's own booking, denormalized for the My Bookings list."""

    id: int
    space_slot_id: int
    space_id: int
    space_name: str
    booking_date: date
    weekday: int
    start_time: time
    end_time: time
    status: str
    waitlist_position: int | None = None


class AdminBookingRead(BaseModel):
    id: int
    space_slot_id: int
    member_id: int
    member_name: str
    booking_date: date
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
