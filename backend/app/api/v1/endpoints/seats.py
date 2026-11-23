"""Seats the club owes money back on, and payments that came too late (#603).

A seat is a registration or a space booking. Both carry the same refund and
late-payment columns (#591, #603), so the club sees them in one list each, with
a type column and a link to the activity or the space.
"""

from datetime import datetime, timezone
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.authorization import require_permission
from app.core.pagination import PageMeta
from app.db.session import get_db
from app.domains.activities.models import Registration
from app.domains.auth.models import User
from app.domains.billing.seat_schemas import (
    LatePaymentResponse,
    RefundResponse,
    RefundReturnedRequest,
    SeatKind,
)
from app.domains.billing.seats import SeatError, mark_refund_returned
from app.domains.bookings.billing import booking_description
from app.domains.bookings.models import Booking, SpaceSlot
from app.domains.members.models import Member

router = APIRouter(prefix="/seats", tags=["seats"])

_MODELS = {"registration": Registration, "booking": Booking}


def _person_name(seat) -> str | None:
    person = seat.member.person if seat.member else None
    return f"{person.first_name} {person.last_name}" if person else None


def _owner(seat) -> tuple[int, str]:
    """What the seat belongs to: its activity, or its space and slot."""
    if isinstance(seat, Registration):
        return seat.activity_id, seat.activity.name
    slot = seat.slot
    return slot.space_id, booking_description(slot.space, slot)


def _kind(seat) -> SeatKind:
    return "registration" if isinstance(seat, Registration) else "booking"


def _refund_response(seat) -> RefundResponse:
    receipt = next(
        r for r in sorted(seat.receipts, key=lambda r: -r.id)
        if r.is_active and r.document_type == "invoice" and r.status == "paid"
    )
    owner_id, owner_name = _owner(seat)
    return RefundResponse(
        kind=_kind(seat),
        seat_id=seat.id,
        owner_id=owner_id,
        owner_name=owner_name,
        member_name=_person_name(seat),
        member_number=seat.member.member_number if seat.member else None,
        cancelled_at=seat.cancelled_at,
        refund_status=seat.refund_status,
        receipt_id=receipt.id,
        receipt_number=receipt.receipt_number,
        amount=float(receipt.total_amount),
        payment_method=receipt.payment_method,
        payment_date=receipt.payment_date,
        gateway_reference=(
            receipt.stripe_payment_intent_id
            or receipt.redsys_auth_code
            or receipt.transaction_id
        ),
        refund_returned_at=seat.refund_returned_at,
        refund_credit_note_id=seat.refund_credit_note_id,
    )


def _registrations(db: Session):
    return db.query(Registration).options(
        joinedload(Registration.member).joinedload(Member.person),
        joinedload(Registration.activity),
        selectinload(Registration.receipts),
    )


def _bookings(db: Session):
    return db.query(Booking).options(
        joinedload(Booking.member).joinedload(Member.person),
        joinedload(Booking.slot).joinedload(SpaceSlot.space),
        selectinload(Booking.receipts),
    )


def _latest_first(seats: list, key: str) -> list:
    oldest = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(seats, key=lambda s: getattr(s, key) or oldest, reverse=True)


@router.get("/refunds")
def list_refunds(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    refund_status: str = Query("due", pattern="^(due|returned)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("billing.read")),
):
    """Cancelled seats whose payment is owed back, or was returned, latest first.

    Carries what finds the money in the gateway: the method, the date and the
    reference the provider gave the payment. Two tables, merged here: a club's
    refunds are few enough to read whole.
    """
    seats = _latest_first(
        _registrations(db).filter(Registration.refund_status == refund_status).all()
        + _bookings(db).filter(Booking.refund_status == refund_status).all(),
        "cancelled_at",
    )
    total = len(seats)
    window = seats[(page - 1) * per_page : page * per_page]
    meta = PageMeta(
        page=page,
        per_page=per_page,
        total=total,
        total_pages=ceil(total / per_page) if total else 1,
    )
    return {"meta": meta.model_dump(), "items": [_refund_response(s) for s in window]}


@router.get("/late-payments")
def list_unseen_late_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("billing.read")),
):
    """Payments that arrived after their seat was released, not yet looked at.

    What the dashboard banner shows until an organiser acknowledges each one.
    """
    seats = _latest_first(
        _registrations(db)
        .filter(
            Registration.late_payment_at.isnot(None),
            Registration.late_payment_seen_at.is_(None),
        )
        .all()
        + _bookings(db)
        .filter(
            Booking.late_payment_at.isnot(None),
            Booking.late_payment_seen_at.is_(None),
        )
        .all(),
        "late_payment_at",
    )
    items = []
    for seat in seats:
        owner_id, owner_name = _owner(seat)
        items.append(
            LatePaymentResponse(
                kind=_kind(seat),
                seat_id=seat.id,
                owner_id=owner_id,
                owner_name=owner_name,
                member_name=_person_name(seat),
                status=seat.status,
                refund_status=seat.refund_status,
                late_payment_at=seat.late_payment_at,
            )
        )
    return {"items": items}


def _seat_or_404(db: Session, kind: SeatKind, seat_id: int):
    model = _MODELS[kind]
    seat = db.query(model).filter(model.id == seat_id).first()
    if seat is None:
        raise HTTPException(status_code=404, detail="Seat not found")
    return seat


@router.post("/{kind}/{seat_id}/refund-returned", response_model=RefundResponse)
def mark_seat_refund_returned(
    kind: SeatKind,
    seat_id: int,
    data: RefundReturnedRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("billing.write")),
):
    """Record that the money owed back on a cancelled seat has been returned."""
    seat = _seat_or_404(db, kind, seat_id)
    try:
        mark_refund_returned(
            db, seat, current_user.id, data.credit_note_id if data else None
        )
    except SeatError as e:
        raise HTTPException(status_code=400, detail=e.detail)
    db.commit()
    db.refresh(seat)
    return _refund_response(seat)


@router.post(
    "/{kind}/{seat_id}/late-payment-seen", status_code=status.HTTP_204_NO_CONTENT
)
def acknowledge_late_payment(
    kind: SeatKind,
    seat_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("billing.write")),
):
    """Take a late payment off the banner once an organiser has looked at it."""
    seat = _seat_or_404(db, kind, seat_id)
    if seat.late_payment_at is None:
        raise HTTPException(status_code=404, detail="No late payment on this seat")
    seat.late_payment_seen_at = datetime.now(timezone.utc)
    db.commit()
