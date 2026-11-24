"""The club's view of seats that carry money: refunds owed, late payments.

A seat is a registration or a space booking (#603); ``kind`` says which, and
``owner_id`` / ``owner_name`` are its activity or its space and slot.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

SeatKind = Literal["registration", "booking"]


class RefundReturnedRequest(BaseModel):
    credit_note_id: int | None = None


class RefundResponse(BaseModel):
    """A cancelled seat whose payment is owed back, and what finds the money."""

    kind: SeatKind
    seat_id: int
    owner_id: int
    owner_name: str
    member_name: str | None = None
    member_number: str | None = None
    cancelled_at: datetime | None = None
    refund_status: str
    receipt_id: int
    receipt_number: str
    amount: float
    payment_method: str | None = None
    payment_date: date | None = None
    gateway_reference: str | None = None
    refund_returned_at: datetime | None = None
    refund_credit_note_id: int | None = None


class LatePaymentResponse(BaseModel):
    """A payment that arrived after its seat was released, not yet looked at."""

    kind: SeatKind
    seat_id: int
    owner_id: int
    owner_name: str
    member_name: str | None = None
    status: str
    refund_status: str
    late_payment_at: datetime
