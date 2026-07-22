"""Simple Bookings service — spaces, slots, availability, book/waitlist/cancel.

Following the house convention, nothing here commits — the endpoint does.

Capacity is enforced under a ``SELECT … FOR UPDATE`` lock on the parent
``space_slots`` row: a slot-instance (slot + date) has no row of its own, so the
slot row is the serialization point for both the capacity count and FIFO
promotion. The per-member partial unique index is the backstop against a member
double-submitting.
"""

import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func
from sqlalchemy.orm import Query, Session, joinedload

from app.domains.bookings.models import Booking, Space, SpaceSlot
from app.domains.bookings.notifications import (
    BookingNotification,
    BookingNotifier,
    NullBookingNotifier,
)
from app.domains.bookings.schemas import (
    SpaceCreate,
    SpaceSlotCreate,
    SpaceSlotUpdate,
    SpaceUpdate,
)
from app.domains.members.models import Member
from app.domains.organizations.models import OrganizationSettings
from app.domains.shared.enums import BookingStatus

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = (BookingStatus.BOOKED, BookingStatus.WAITLISTED)


# --- Errors ---------------------------------------------------------------


class BookingError(Exception):
    """Base class for booking domain errors."""


class SpaceNotFound(BookingError):
    pass


class SlotNotFound(BookingError):
    pass


class SlotOutsideOpeningHours(BookingError):
    pass


class SlotOverlap(BookingError):
    pass


class SlotFull(BookingError):
    pass


class WeekdayMismatch(BookingError):
    pass


class BookingInPast(BookingError):
    pass


class BookingWindowExceeded(BookingError):
    pass


class DuplicateBooking(BookingError):
    pass


class CancellationTooLate(BookingError):
    pass


class NotCancellable(BookingError):
    pass


# --- Settings / time helpers ---------------------------------------------


def _org(db: Session) -> OrganizationSettings | None:
    return db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()


def _features(db: Session) -> dict:
    org = _org(db)
    return (org.features or {}) if org else {}


def _locale(db: Session) -> str:
    org = _org(db)
    return (org.locale if org and org.locale else "es")


def _tz(db: Session) -> ZoneInfo:
    org = _org(db)
    name = (org.timezone if org and org.timezone else "Europe/Madrid")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("Europe/Madrid")


def _window_days(db: Session) -> int:
    return int(_features(db).get("booking_window_days", 14))


def _deadline_hours(db: Session) -> int:
    return int(_features(db).get("booking_cancellation_deadline_hours", 24))


def _waitlist_enabled(db: Session) -> bool:
    return bool(_features(db).get("booking_waitlist_enabled", True))


# --- Spaces ---------------------------------------------------------------


def list_spaces(db: Session, *, active_only: bool = False) -> list[Space]:
    query = db.query(Space)
    if active_only:
        query = query.filter(Space.is_active.is_(True))
    return query.order_by(Space.name, Space.id).all()


def get_space(db: Session, space_id: int) -> Space | None:
    return db.query(Space).filter(Space.id == space_id).first()


def create_space(db: Session, data: SpaceCreate) -> Space:
    space = Space(
        name=data.name,
        space_type=data.space_type,
        description=data.description,
        open_time=data.open_time,
        close_time=data.close_time,
        is_active=data.is_active,
    )
    db.add(space)
    return space


def update_space(db: Session, space: Space, data: SpaceUpdate) -> Space:
    payload = data.model_dump(exclude_unset=True)
    for key, value in payload.items():
        setattr(space, key, value)
    if space.close_time <= space.open_time:
        raise SlotOutsideOpeningHours("close_time must be after open_time")
    return space


def deactivate_space(db: Session, space: Space) -> Space:
    space.is_active = False
    return space


# --- Slots ----------------------------------------------------------------


def list_slots(db: Session, space_id: int) -> list[SpaceSlot]:
    return (
        db.query(SpaceSlot)
        .filter(SpaceSlot.space_id == space_id)
        .order_by(SpaceSlot.weekday, SpaceSlot.start_time)
        .all()
    )


def get_slot(db: Session, space_id: int, slot_id: int) -> SpaceSlot | None:
    return (
        db.query(SpaceSlot)
        .filter(SpaceSlot.id == slot_id, SpaceSlot.space_id == space_id)
        .first()
    )


def _validate_slot(
    db: Session,
    space: Space,
    *,
    weekday: int,
    start_time,
    end_time,
    exclude_slot_id: int | None = None,
) -> None:
    if not (space.open_time <= start_time and end_time <= space.close_time):
        raise SlotOutsideOpeningHours(
            "Slot must fall within the space's opening hours"
        )
    # No overlap with another active slot on the same weekday.
    others = (
        db.query(SpaceSlot)
        .filter(
            SpaceSlot.space_id == space.id,
            SpaceSlot.weekday == weekday,
            SpaceSlot.is_active.is_(True),
        )
        .all()
    )
    for other in others:
        if exclude_slot_id is not None and other.id == exclude_slot_id:
            continue
        if start_time < other.end_time and other.start_time < end_time:
            raise SlotOverlap("Slot overlaps an existing slot on this weekday")


def create_slot(db: Session, space: Space, data: SpaceSlotCreate) -> SpaceSlot:
    _validate_slot(
        db,
        space,
        weekday=data.weekday,
        start_time=data.start_time,
        end_time=data.end_time,
    )
    slot = SpaceSlot(
        space_id=space.id,
        weekday=data.weekday,
        start_time=data.start_time,
        end_time=data.end_time,
        capacity=data.capacity,
        is_active=data.is_active,
    )
    db.add(slot)
    return slot


def update_slot(
    db: Session, space: Space, slot: SpaceSlot, data: SpaceSlotUpdate
) -> SpaceSlot:
    payload = data.model_dump(exclude_unset=True)
    weekday = payload.get("weekday", slot.weekday)
    start_time = payload.get("start_time", slot.start_time)
    end_time = payload.get("end_time", slot.end_time)
    if end_time <= start_time:
        raise SlotOutsideOpeningHours("end_time must be after start_time")
    _validate_slot(
        db,
        space,
        weekday=weekday,
        start_time=start_time,
        end_time=end_time,
        exclude_slot_id=slot.id,
    )
    for key, value in payload.items():
        setattr(slot, key, value)
    return slot


def delete_slot(db: Session, slot: SpaceSlot) -> None:
    db.delete(slot)


# --- Counts ---------------------------------------------------------------


def _count(db: Session, slot_id: int, on: date, status: str) -> int:
    return (
        db.query(func.count(Booking.id))
        .filter(
            Booking.space_slot_id == slot_id,
            Booking.booking_date == on,
            Booking.status == status,
        )
        .scalar()
        or 0
    )


def _member_active_booking(
    db: Session, slot_id: int, on: date, member_id: int
) -> Booking | None:
    return (
        db.query(Booking)
        .filter(
            Booking.space_slot_id == slot_id,
            Booking.booking_date == on,
            Booking.member_id == member_id,
            Booking.status.in_(ACTIVE_STATUSES),
        )
        .first()
    )


# --- Availability ---------------------------------------------------------


def space_week_availability(
    db: Session, space: Space, week_start: date, member_id: int | None
) -> list[dict]:
    """One cell per active slot, placed on the date its weekday falls in the week.

    ``week_start`` should be the Monday of the target ISO week; each slot occurs
    on ``week_start + weekday``.
    """
    tz = _tz(db)
    now_local = datetime.now(tz)
    today = now_local.date()
    window_end = today + timedelta(days=_window_days(db))

    slots = [s for s in list_slots(db, space.id) if s.is_active]
    cells: list[dict] = []
    for slot in slots:
        on = week_start + timedelta(days=slot.weekday)
        booked = _count(db, slot.id, on, BookingStatus.BOOKED)
        waitlisted = _count(db, slot.id, on, BookingStatus.WAITLISTED)

        my_status = "none"
        if member_id is not None:
            mine = _member_active_booking(db, slot.id, on, member_id)
            if mine is not None:
                my_status = mine.status

        slot_start = datetime.combine(on, slot.start_time, tzinfo=tz)
        if slot_start <= now_local:
            cell_state = "past"
        elif on > window_end:
            cell_state = "out_of_window"
        elif booked >= slot.capacity:
            cell_state = "full"
        else:
            cell_state = "open"

        cells.append(
            {
                "space_slot_id": slot.id,
                "date": on,
                "weekday": slot.weekday,
                "start_time": slot.start_time,
                "end_time": slot.end_time,
                "capacity": slot.capacity,
                "booked_count": booked,
                "waitlist_count": waitlisted,
                "my_status": my_status,
                "cell_state": cell_state,
            }
        )
    return cells


# --- Book / cancel --------------------------------------------------------


def _notification(
    db: Session, booking: Booking, slot: SpaceSlot, space: Space, member: Member, **extra
) -> BookingNotification:
    person = member.person
    to = person.email if person else None
    name = person.first_name if person else ""
    time_str = f"{slot.start_time.strftime('%H:%M')}–{slot.end_time.strftime('%H:%M')}"
    return BookingNotification(
        to=to,
        member_name=name,
        space_name=space.name,
        date_str=booking.booking_date.strftime("%d/%m/%Y"),
        time_str=time_str,
        locale=_locale(db),
        **extra,
    )


def create_booking(
    db: Session,
    member: Member,
    space_slot_id: int,
    booking_date: date,
    *,
    notifier: BookingNotifier | None = None,
) -> Booking:
    """Book a slot-instance, or waitlist it when full. Returns the new booking."""
    notifier = notifier or NullBookingNotifier()

    # Lock the slot row: serializes the capacity count + any concurrent booking.
    slot = (
        db.query(SpaceSlot)
        .filter(SpaceSlot.id == space_slot_id)
        .with_for_update()
        .first()
    )
    if slot is None or not slot.is_active:
        raise SlotNotFound(str(space_slot_id))
    space = get_space(db, slot.space_id)
    if space is None or not space.is_active:
        raise SlotNotFound(str(space_slot_id))

    if booking_date.weekday() != slot.weekday:
        raise WeekdayMismatch("booking_date does not fall on the slot's weekday")

    tz = _tz(db)
    now_local = datetime.now(tz)
    slot_start = datetime.combine(booking_date, slot.start_time, tzinfo=tz)
    if slot_start <= now_local:
        raise BookingInPast("Slot has already started")
    if booking_date > now_local.date() + timedelta(days=_window_days(db)):
        raise BookingWindowExceeded("Beyond the booking window")

    if _member_active_booking(db, slot.id, booking_date, member.id) is not None:
        raise DuplicateBooking("Member already holds this slot-instance")

    booked = _count(db, slot.id, booking_date, BookingStatus.BOOKED)
    if booked < slot.capacity:
        status = BookingStatus.BOOKED
        waitlisted_at = None
    elif _waitlist_enabled(db):
        status = BookingStatus.WAITLISTED
        waitlisted_at = now_local
    else:
        raise SlotFull("Slot is full and the waitlist is disabled")

    booking = Booking(
        space_slot_id=slot.id,
        member_id=member.id,
        booking_date=booking_date,
        status=status,
        waitlisted_at=waitlisted_at,
    )
    db.add(booking)
    db.flush()

    if status == BookingStatus.BOOKED:
        notifier.send_confirmation(
            _notification(
                db,
                booking,
                slot,
                space,
                member,
                cancellation_deadline_hours=_deadline_hours(db),
            )
        )
    else:
        position = _count(db, slot.id, booking_date, BookingStatus.WAITLISTED)
        notifier.send_waitlisted(
            _notification(db, booking, slot, space, member, position=position)
        )
    return booking


def cancel_booking(
    db: Session,
    booking: Booking,
    *,
    cancelled_by_user_id: int,
    is_admin: bool,
    notifier: BookingNotifier | None = None,
) -> Booking:
    """Cancel a booking; promote the earliest waitlisted member if a seat frees."""
    notifier = notifier or NullBookingNotifier()

    if booking.status == BookingStatus.CANCELLED:
        raise NotCancellable("Booking is already cancelled")

    # Lock the slot row so the promotion count is race-safe.
    slot = (
        db.query(SpaceSlot)
        .filter(SpaceSlot.id == booking.space_slot_id)
        .with_for_update()
        .first()
    )
    tz = _tz(db)
    now_local = datetime.now(tz)

    if not is_admin:
        slot_start = datetime.combine(booking.booking_date, slot.start_time, tzinfo=tz)
        deadline = slot_start - timedelta(hours=_deadline_hours(db))
        if now_local >= deadline:
            raise CancellationTooLate("Past the cancellation deadline")

    was_booked = booking.status == BookingStatus.BOOKED
    booking.status = BookingStatus.CANCELLED
    booking.cancelled_at = now_local
    booking.cancelled_by_user_id = cancelled_by_user_id
    db.flush()

    if was_booked:
        booked = _count(db, slot.id, booking.booking_date, BookingStatus.BOOKED)
        if booked < slot.capacity:
            promoted = (
                db.query(Booking)
                .filter(
                    Booking.space_slot_id == slot.id,
                    Booking.booking_date == booking.booking_date,
                    Booking.status == BookingStatus.WAITLISTED,
                )
                .order_by(Booking.waitlisted_at.asc(), Booking.id.asc())
                .first()
            )
            if promoted is not None:
                promoted.status = BookingStatus.BOOKED
                promoted.waitlisted_at = None
                db.flush()
                space = get_space(db, slot.space_id)
                member = (
                    db.query(Member)
                    .options(joinedload(Member.person))
                    .filter(Member.id == promoted.member_id)
                    .first()
                )
                if member is not None and space is not None:
                    notifier.send_promoted(
                        _notification(db, promoted, slot, space, member)
                    )
    return booking


# --- Reads ----------------------------------------------------------------


def my_bookings(db: Session, member_id: int, *, scope: str) -> list[dict]:
    """A member's non-cancelled bookings, denormalized, upcoming or past."""
    tz = _tz(db)
    today = datetime.now(tz).date()

    query = (
        db.query(Booking)
        .options(joinedload(Booking.slot).joinedload(SpaceSlot.space))
        .filter(
            Booking.member_id == member_id,
            Booking.status.in_(ACTIVE_STATUSES),
        )
    )
    if scope == "past":
        query = query.filter(Booking.booking_date < today).order_by(
            Booking.booking_date.desc()
        )
    else:
        query = query.filter(Booking.booking_date >= today).order_by(
            Booking.booking_date.asc()
        )

    out: list[dict] = []
    for b in query.all():
        slot = b.slot
        space = slot.space
        position = None
        if b.status == BookingStatus.WAITLISTED:
            ahead = (
                db.query(func.count(Booking.id))
                .filter(
                    Booking.space_slot_id == b.space_slot_id,
                    Booking.booking_date == b.booking_date,
                    Booking.status == BookingStatus.WAITLISTED,
                    Booking.waitlisted_at < b.waitlisted_at,
                )
                .scalar()
                or 0
            )
            position = ahead + 1
        out.append(
            {
                "id": b.id,
                "space_slot_id": b.space_slot_id,
                "space_id": space.id,
                "space_name": space.name,
                "booking_date": b.booking_date,
                "weekday": slot.weekday,
                "start_time": slot.start_time,
                "end_time": slot.end_time,
                "status": b.status,
                "waitlist_position": position,
            }
        )
    return out


def build_space_bookings_query(
    db: Session, space_id: int, *, on: date | None = None, status: str | None = None
) -> Query:
    query = (
        db.query(Booking)
        .join(SpaceSlot, Booking.space_slot_id == SpaceSlot.id)
        .options(
            joinedload(Booking.slot),
            joinedload(Booking.member).joinedload(Member.person),
        )
        .filter(SpaceSlot.space_id == space_id)
    )
    if on is not None:
        query = query.filter(Booking.booking_date == on)
    if status:
        query = query.filter(Booking.status == status)
    return query.order_by(Booking.booking_date.desc(), Booking.id.desc())


def get_booking(db: Session, booking_id: int) -> Booking | None:
    return (
        db.query(Booking)
        .options(
            joinedload(Booking.slot).joinedload(SpaceSlot.space),
            joinedload(Booking.member).joinedload(Member.person),
        )
        .filter(Booking.id == booking_id)
        .first()
    )
