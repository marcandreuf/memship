"""Simple Bookings schemas."""

from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.pagination import PageMeta
from app.core.schema_types import NonBlank, refuse_null
from app.domains.activities.schemas import (
    AUTO_CANCEL_MAX_HOURS,
    PaymentMethod,
    unique_methods,
)


# --- Spaces ---------------------------------------------------------------


class SpaceCreate(BaseModel):
    name: NonBlank(200)
    space_type: str | None = Field(default=None, max_length=50)
    description: str | None = None
    # Price per booking, before VAT. None or 0 means the space is free and no
    # receipt is ever raised for it. Typed like ActivityPrice.amount.
    price: float | None = Field(default=None, ge=0)
    open_time: time
    close_time: time
    # Empty or omitted means the space is open to every member.
    allowed_membership_types: list[int] | None = None
    is_active: bool = True
    # How a paid booking may be paid (#603). A new space is pay-to-confirm: a
    # paid booking is held until its receipt is paid.
    payment_methods: list[PaymentMethod] = []
    # Override of the club's booking auto-cancel default; None inherits it.
    auto_cancel_enabled: bool | None = None
    auto_cancel_hours: int | None = Field(default=None, ge=1, le=AUTO_CANCEL_MAX_HOURS)

    _unique_methods = field_validator("payment_methods")(unique_methods)

    @model_validator(mode="after")
    def _hours(self):
        if self.close_time <= self.open_time:
            raise ValueError("close_time must be after open_time")
        return self


class SpaceUpdate(BaseModel):
    name: NonBlank(200) | None = None
    space_type: str | None = Field(default=None, max_length=50)
    description: str | None = None
    price: float | None = Field(default=None, ge=0)
    open_time: time | None = None
    close_time: time | None = None
    allowed_membership_types: list[int] | None = None
    is_active: bool | None = None
    # One way only: a legacy space may move to pay-to-confirm, never back, and
    # only bookings made afterwards follow it (#603).
    payment_flow: Literal["pay_to_confirm"] | None = None
    payment_methods: list[PaymentMethod] | None = None
    auto_cancel_enabled: bool | None = None
    auto_cancel_hours: int | None = Field(default=None, ge=1, le=AUTO_CANCEL_MAX_HOURS)

    _name_not_null = field_validator("name")(refuse_null)
    _unique_methods = field_validator("payment_methods")(unique_methods)


class SpaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    space_type: str | None
    description: str | None
    price: float | None
    open_time: time
    close_time: time
    allowed_membership_types: list[int] | None
    is_active: bool
    payment_flow: str
    payment_methods: list[str]
    auto_cancel_enabled: bool | None
    auto_cancel_hours: int | None
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
    # Overrides the space's price for this slot; None falls back to the space.
    price: float | None = Field(default=None, ge=0)
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
    price: float | None = Field(default=None, ge=0)
    is_active: bool | None = None


class SpaceSlotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    space_id: int
    slot_date: date
    start_time: time
    end_time: time
    capacity: int
    price: float | None
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
    party_id: int
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
    can_cancel: bool
    # A booking held until paid: when it must be paid by, and its receipt.
    payment_due_at: datetime | None = None
    receipt_id: int | None = None


class AdminBookingRead(BaseModel):
    id: int
    space_slot_id: int
    party_id: int
    member_name: str
    slot_date: date
    start_time: time
    end_time: time
    status: str
    # The payment side (#603): its deadline while pending, its receipt, and
    # whether the club owes money back or a payment came too late.
    payment_due_at: datetime | None = None
    receipt_id: int | None = None
    receipt_status: str | None = None
    receipt_due_date: date | None = None
    refund_status: str = "none"
    late_payment_at: datetime | None = None
    cancelled_cause: str | None = None


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
    # What this slot costs the member: the slot's own price, or the space's,
    # or 0 when neither is set. Shown before the booking is confirmed.
    price: float
    # When a paid booking taken now would have to be paid by, in a
    # pay-to-confirm space (#603). None when booking it costs nothing upfront.
    pay_by: datetime | None = None
    # Seats held, paid or pending payment.
    booked_count: int
    waitlist_count: int
    # none | booked | pending | waitlisted
    my_status: str
    # open | full | past | out_of_window | too_late (too close to the start to
    # be held until paid)
    cell_state: str


class WeekAvailability(BaseModel):
    space_id: int
    week_start: date
    # False when the space is restricted to membership types the member does not
    # hold. The cells are still returned so the week reads normally, but nothing
    # in it can be booked — the reason code says which of the two failures it is:
    # membership_type_not_allowed | no_membership_type
    eligible: bool = True
    ineligible_reason: str | None = None
    cells: list[AvailabilityCell]


# --- Dashboard stats ------------------------------------------------------


class SpacePaymentOptions(BaseModel):
    """What the space form may offer: the methods the club can take today, the
    club's booking auto-cancel default, and which booking mails are off."""

    usable_methods: list[str]
    auto_cancel_enabled: bool
    auto_cancel_hours: int
    switched_off_templates: list[str]


class SpaceStats(BaseModel):
    window_days: int
    booked: int
    pending: int
    waitlisted: int
    cancelled: int
    total: int
    active_spaces: int
    slots: int
    capacity: int
    occupancy_pct: float
