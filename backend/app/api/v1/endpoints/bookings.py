"""Simple Bookings endpoints — admin space/slot management + member bookings.

All endpoints return 404 when ``features.bookings`` is off, so a disabled module
is invisible rather than merely forbidden (the member-card / custom-fields gate).
Admins manage spaces, slots and view all bookings; members book slots on the
per-space week calendar and manage their own reservations.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.authorization import require_admin
from app.core.pagination import paginate
from app.core.security.dependencies import get_current_user
from app.db.session import get_db
from app.domains.auth.models import User
from app.domains.bookings import service
from app.domains.bookings.notifications import EmailBookingNotifier
from app.domains.bookings.schemas import (
    AdminBookingPage,
    AdminBookingRead,
    BookingCreate,
    BookingRead,
    MyBookingRead,
    SpaceCreate,
    SpaceRead,
    SpaceSlotCreate,
    SpaceSlotRead,
    SpaceSlotUpdate,
    SpaceUpdate,
    WeekAvailability,
)
from app.domains.members.models import Member
from app.domains.organizations.models import OrganizationSettings

router = APIRouter(prefix="/spaces", tags=["bookings"])
member_router = APIRouter(tags=["bookings"])

_notifier = EmailBookingNotifier()


def _require_bookings_enabled(db: Session) -> None:
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    features = (org.features or {}) if org else {}
    if not features.get("bookings"):
        raise HTTPException(status_code=404, detail="Not found")


def _current_member(db: Session, user: User) -> Member:
    member = (
        db.query(Member)
        .options(joinedload(Member.person))
        .filter(Member.user_id == user.id)
        .first()
    )
    if member is None:
        raise HTTPException(status_code=403, detail="No member profile")
    return member


def _load_space_or_404(db: Session, space_id: int) -> "service.Space":
    space = service.get_space(db, space_id)
    if space is None:
        raise HTTPException(status_code=404, detail="Space not found")
    return space


def _slot_error_422(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=[{"loc": ["body"], "msg": str(exc), "type": "value_error"}],
    )


# --- Admin: spaces --------------------------------------------------------


@router.get("", response_model=list[SpaceRead])
def list_spaces_admin(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    _require_bookings_enabled(db)
    return service.list_spaces(db)


@router.post("", response_model=SpaceRead, status_code=status.HTTP_201_CREATED)
def create_space(
    data: SpaceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    _require_bookings_enabled(db)
    space = service.create_space(db, data)
    db.commit()
    db.refresh(space)
    return space


@router.get("/{space_id}", response_model=SpaceRead)
def get_space_admin(
    space_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    _require_bookings_enabled(db)
    return _load_space_or_404(db, space_id)


@router.put("/{space_id}", response_model=SpaceRead)
def update_space(
    space_id: int,
    data: SpaceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    _require_bookings_enabled(db)
    space = _load_space_or_404(db, space_id)
    try:
        service.update_space(db, space, data)
    except service.BookingError as exc:
        raise _slot_error_422(exc)
    db.commit()
    db.refresh(space)
    return space


@router.delete("/{space_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_space(
    space_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    _require_bookings_enabled(db)
    space = _load_space_or_404(db, space_id)
    service.deactivate_space(db, space)
    db.commit()


# --- Admin: slots ---------------------------------------------------------


@router.get("/{space_id}/slots", response_model=list[SpaceSlotRead])
def list_slots(
    space_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    _require_bookings_enabled(db)
    _load_space_or_404(db, space_id)
    return service.list_slots(db, space_id)


@router.post(
    "/{space_id}/slots",
    response_model=SpaceSlotRead,
    status_code=status.HTTP_201_CREATED,
)
def create_slot(
    space_id: int,
    data: SpaceSlotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    _require_bookings_enabled(db)
    space = _load_space_or_404(db, space_id)
    try:
        slot = service.create_slot(db, space, data)
    except service.BookingError as exc:
        raise _slot_error_422(exc)
    db.commit()
    db.refresh(slot)
    return slot


@router.put("/{space_id}/slots/{slot_id}", response_model=SpaceSlotRead)
def update_slot(
    space_id: int,
    slot_id: int,
    data: SpaceSlotUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    _require_bookings_enabled(db)
    space = _load_space_or_404(db, space_id)
    slot = service.get_slot(db, space_id, slot_id)
    if slot is None:
        raise HTTPException(status_code=404, detail="Slot not found")
    try:
        service.update_slot(db, space, slot, data)
    except service.BookingError as exc:
        raise _slot_error_422(exc)
    db.commit()
    db.refresh(slot)
    return slot


@router.delete(
    "/{space_id}/slots/{slot_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_slot(
    space_id: int,
    slot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    _require_bookings_enabled(db)
    _load_space_or_404(db, space_id)
    slot = service.get_slot(db, space_id, slot_id)
    if slot is None:
        raise HTTPException(status_code=404, detail="Slot not found")
    service.delete_slot(db, slot)
    db.commit()


# --- Admin: bookings for a space -----------------------------------------


@router.get("/{space_id}/bookings", response_model=AdminBookingPage)
def list_space_bookings(
    space_id: int,
    on: date | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    _require_bookings_enabled(db)
    _load_space_or_404(db, space_id)
    query = service.build_space_bookings_query(
        db, space_id, on=on, status=status_filter
    )
    items, meta = paginate(query, page, per_page)
    rows = []
    for b in items:
        person = b.member.person if b.member else None
        name = (
            f"{person.first_name} {person.last_name}".strip() if person else ""
        )
        rows.append(
            AdminBookingRead(
                id=b.id,
                space_slot_id=b.space_slot_id,
                member_id=b.member_id,
                member_name=name,
                booking_date=b.booking_date,
                start_time=b.slot.start_time,
                end_time=b.slot.end_time,
                status=b.status,
            )
        )
    return AdminBookingPage(meta=meta, items=rows)


# --- Member: availability + booking --------------------------------------


@member_router.get("/spaces-available", response_model=list[SpaceRead])
def list_spaces_member(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Active spaces, for the member's space picker."""
    _require_bookings_enabled(db)
    return service.list_spaces(db, active_only=True)


@member_router.get(
    "/spaces/{space_id}/availability", response_model=WeekAvailability
)
def get_availability(
    space_id: int,
    week_start: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_bookings_enabled(db)
    space = service.get_space(db, space_id)
    if space is None or not space.is_active:
        raise HTTPException(status_code=404, detail="Space not found")
    member = _current_member(db, current_user)
    cells = service.space_week_availability(db, space, week_start, member.id)
    return WeekAvailability(space_id=space_id, week_start=week_start, cells=cells)


@member_router.post(
    "/bookings", response_model=BookingRead, status_code=status.HTTP_201_CREATED
)
def create_booking(
    data: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_bookings_enabled(db)
    member = _current_member(db, current_user)
    try:
        booking = service.create_booking(
            db,
            member,
            data.space_slot_id,
            data.booking_date,
            notifier=_notifier,
        )
    except service.SlotNotFound:
        raise HTTPException(status_code=404, detail="Slot not found")
    except (service.SlotFull, service.DuplicateBooking) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except (
        service.WeekdayMismatch,
        service.BookingInPast,
        service.BookingWindowExceeded,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    db.commit()
    db.refresh(booking)
    return booking


@member_router.get("/me/bookings", response_model=list[MyBookingRead])
def get_my_bookings(
    scope: str = "upcoming",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_bookings_enabled(db)
    member = _current_member(db, current_user)
    scope = scope if scope in ("upcoming", "past") else "upcoming"
    return service.my_bookings(db, member.id, scope=scope)


@member_router.delete(
    "/bookings/{booking_id}", status_code=status.HTTP_204_NO_CONTENT
)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_bookings_enabled(db)
    booking = service.get_booking(db, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    is_admin = current_user.role in ("super_admin", "admin", "restricted")
    if not is_admin:
        member = _current_member(db, current_user)
        if booking.member_id != member.id:
            raise HTTPException(status_code=403, detail="Not your booking")

    try:
        service.cancel_booking(
            db,
            booking,
            cancelled_by_user_id=current_user.id,
            is_admin=is_admin,
            notifier=_notifier,
        )
    except service.CancellationTooLate as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    except service.NotCancellable as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    db.commit()
