"""Simple Bookings service — spaces, dated slots, availability, book/waitlist/cancel.

Following the house convention, nothing here commits — the endpoint does.

Capacity is enforced under a ``SELECT … FOR UPDATE`` lock on the ``space_slots``
row, which is the serialization point for both the capacity count and FIFO
promotion. The per-member partial unique index is the backstop against a member
double-submitting.

Slots live on concrete dates. A create with a repeat rule materializes every
occurrence up front (bounded by the rule's count) and stamps them with a shared
``series_id``; an edit can then target one occurrence or this-and-upcoming.
"""

import logging
from datetime import date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func
from sqlalchemy.orm import Query, Session, joinedload

from app.domains.bookings.billing import (
    booking_price,
    ensure_booking_receipt,
    void_booking_receipts,
)
from app.domains.bookings.eligibility import check_space_eligibility
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


class SlotInPast(BookingError):
    pass


class BookingInPast(BookingError):
    pass


class BookingWindowExceeded(BookingError):
    pass


class DuplicateBooking(BookingError):
    pass


class NotEligible(BookingError):
    """The member's membership type does not allow booking this space.

    Carries the reason code from ``eligibility`` so the caller can tell
    "your tier is not on the list" apart from "you have no tier".
    """

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


class CancellationTooLate(BookingError):
    pass


class NotCancellable(BookingError):
    pass


class HasActiveBookings(BookingError):
    """Deleting would destroy members' active bookings; pass force to proceed."""

    def __init__(self, affected_members: int):
        super().__init__(str(affected_members))
        self.affected_members = affected_members


class SlotsOutsideHours(BookingError):
    """Narrowing a space's hours would leave slots outside them."""

    def __init__(self, slot_count: int, affected_members: int):
        super().__init__(
            f"{slot_count} slot(s) fall outside the new opening hours"
        )
        self.slot_count = slot_count
        self.affected_members = affected_members


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
        price=data.price,
        open_time=data.open_time,
        close_time=data.close_time,
        allowed_membership_types=data.allowed_membership_types or None,
        is_active=data.is_active,
    )
    db.add(space)
    return space


def update_space(
    db: Session,
    space: Space,
    data: SpaceUpdate,
    *,
    force: bool = False,
    notifier: BookingNotifier | None = None,
) -> Space:
    """Update a space. Narrowing its hours is checked against the slots that
    already exist: without ``force`` it refuses when upcoming active slots fall
    outside the new window, so members cannot keep booking a time the space is
    closed; with ``force`` those slots are deleted the way ``delete_slot`` does
    it, and every member holding one is notified."""
    payload = data.model_dump(exclude_unset=True)
    if "allowed_membership_types" in payload:
        # An empty list and NULL both mean "open to everyone"; store one of them
        # so the column has a single reading.
        payload["allowed_membership_types"] = (
            payload["allowed_membership_types"] or None
        )
    for key, value in payload.items():
        setattr(space, key, value)
    if space.close_time <= space.open_time:
        raise SlotOutsideOpeningHours("close_time must be after open_time")

    if payload.keys() & {"open_time", "close_time"}:
        stranded = _slots_outside_hours(db, space)
        if stranded:
            affected = _affected_active_bookings(db, [s.id for s in stranded])
            if not force:
                raise SlotsOutsideHours(
                    len(stranded), len({b.member_id for b in affected})
                )
            for slot in stranded:
                delete_slot(db, slot, force=True, notifier=notifier)
    return space


def _slots_outside_hours(db: Session, space: Space) -> list[SpaceSlot]:
    """Upcoming active slots that start before the space opens or end after it
    closes. Past slots are history and stay as they are."""
    today = datetime.now(_tz(db)).date()
    return (
        db.query(SpaceSlot)
        .filter(
            SpaceSlot.space_id == space.id,
            SpaceSlot.is_active.is_(True),
            SpaceSlot.slot_date >= today,
            (SpaceSlot.start_time < space.open_time)
            | (SpaceSlot.end_time > space.close_time),
        )
        .order_by(SpaceSlot.slot_date, SpaceSlot.start_time)
        .all()
    )


def deactivate_space(db: Session, space: Space) -> Space:
    space.is_active = False
    return space


def _affected_active_bookings(db: Session, slot_ids: list[int]) -> list[Booking]:
    """Active (booked/waitlisted) bookings on today-or-future slots — the members
    a destructive delete would strand. Loaded with member+person+slot so the
    caller can notify before the rows cascade away."""
    if not slot_ids:
        return []
    today = datetime.now(_tz(db)).date()
    return (
        db.query(Booking)
        .join(SpaceSlot, Booking.space_slot_id == SpaceSlot.id)
        .options(
            joinedload(Booking.slot).joinedload(SpaceSlot.space),
            joinedload(Booking.member).joinedload(Member.person),
        )
        .filter(
            Booking.space_slot_id.in_(slot_ids),
            Booking.status.in_(ACTIVE_STATUSES),
            SpaceSlot.slot_date >= today,
        )
        .all()
    )


def delete_space(
    db: Session,
    space: Space,
    *,
    force: bool = False,
    notifier: BookingNotifier | None = None,
) -> list[Booking]:
    """Destructively delete a space (slots + bookings cascade). Without force,
    refuses when members hold active future bookings; with force, every
    affected member is notified before the rows are gone. Deactivation via
    update is the non-destructive default path."""
    notifier = notifier or NullBookingNotifier()
    slot_ids = [s.id for s in space.slots]
    affected = _affected_active_bookings(db, slot_ids)
    if affected and not force:
        raise HasActiveBookings(len({b.member_id for b in affected}))
    for b in affected:
        notifier.send_admin_cancellation(
            _notification(db, b, b.slot, space, b.member)
        )
    db.delete(space)
    return affected


# --- Slots ----------------------------------------------------------------


def list_slots(db: Session, space_id: int) -> list[SpaceSlot]:
    return (
        db.query(SpaceSlot)
        .filter(SpaceSlot.space_id == space_id)
        .order_by(SpaceSlot.slot_date, SpaceSlot.start_time)
        .all()
    )


def get_slot(db: Session, space_id: int, slot_id: int) -> SpaceSlot | None:
    return (
        db.query(SpaceSlot)
        .filter(SpaceSlot.id == slot_id, SpaceSlot.space_id == space_id)
        .first()
    )


def series_sizes_upcoming(slots: list[SpaceSlot]) -> dict[int, int]:
    """Per slot id, how many slots of its series are dated on/after it (itself
    included). One-off slots count as 1. Computed over the given list — callers
    pass a space's full slot list, and a series never crosses spaces."""
    by_series: dict = {}
    for s in slots:
        if s.series_id is not None:
            by_series.setdefault(s.series_id, []).append(s.slot_date)
    return {
        s.id: (
            sum(1 for d in by_series[s.series_id] if d >= s.slot_date)
            if s.series_id is not None
            else 1
        )
        for s in slots
    }


def _validate_slot_on_date(
    db: Session,
    space: Space,
    *,
    slot_date: date,
    start_time,
    end_time,
    exclude_slot_ids: set[int] | None = None,
) -> None:
    if not (space.open_time <= start_time and end_time <= space.close_time):
        raise SlotOutsideOpeningHours(
            f"{slot_date.isoformat()}: slot must fall within the space's opening hours"
        )
    # No overlap with another active slot on the same date.
    others = (
        db.query(SpaceSlot)
        .filter(
            SpaceSlot.space_id == space.id,
            SpaceSlot.slot_date == slot_date,
            SpaceSlot.is_active.is_(True),
        )
        .all()
    )
    for other in others:
        if exclude_slot_ids and other.id in exclude_slot_ids:
            continue
        if start_time < other.end_time and other.start_time < end_time:
            raise SlotOverlap(
                f"{slot_date.isoformat()}: slot overlaps an existing slot"
            )


def _past_guard(db: Session, slot_date: date, start_time) -> None:
    tz = _tz(db)
    now_local = datetime.now(tz)
    if datetime.combine(slot_date, start_time, tzinfo=tz) <= now_local:
        raise SlotInPast(
            f"{slot_date.isoformat()}: slot date and time are in the past"
        )


def _occurrence_dates(data: SpaceSlotCreate) -> list[date]:
    """Concrete dates for a create: the picked date, expanded by the repeat rule.

    Repeat semantics: selected weekdays (defaulting to the picked date's weekday)
    on every Nth week for ``count`` weeks, starting from the picked date's week.
    Dates before the picked date (a selected weekday earlier in week zero) are
    skipped — the picked date is the series' first candidate day.
    """
    if data.repeat is None:
        return [data.slot_date]
    weekdays = sorted(set(data.repeat.weekdays)) or [data.slot_date.weekday()]
    week_monday = data.slot_date - timedelta(days=data.slot_date.weekday())
    dates: list[date] = []
    for i in range(data.repeat.count):
        monday = week_monday + timedelta(weeks=i * data.repeat.interval_weeks)
        for wd in weekdays:
            d = monday + timedelta(days=wd)
            if d >= data.slot_date:
                dates.append(d)
    return dates


def create_slot(db: Session, space: Space, data: SpaceSlotCreate) -> list[SpaceSlot]:
    """Create one dated slot, or a materialized series when a repeat is given.

    All-or-nothing: every occurrence must pass the past guard, opening hours and
    overlap checks (each error names its date) or the whole batch is rejected.
    """
    start_time = space.open_time if data.all_day else data.start_time
    end_time = space.close_time if data.all_day else data.end_time

    dates = _occurrence_dates(data)
    errors: list[str] = []
    for d in dates:
        try:
            _past_guard(db, d, start_time)
            _validate_slot_on_date(
                db, space, slot_date=d, start_time=start_time, end_time=end_time
            )
        except BookingError as exc:
            errors.append(str(exc))
    if errors:
        message = "; ".join(errors)
        if any("overlaps" in e for e in errors):
            raise SlotOverlap(message)
        if any("opening hours" in e for e in errors):
            raise SlotOutsideOpeningHours(message)
        raise SlotInPast(message)

    series_id = uuid4() if data.repeat is not None and len(dates) > 1 else None
    slots = [
        SpaceSlot(
            space_id=space.id,
            slot_date=d,
            start_time=start_time,
            end_time=end_time,
            capacity=data.capacity,
            price=data.price,
            series_id=series_id,
            is_active=data.is_active,
        )
        for d in dates
    ]
    db.add_all(slots)
    return slots


def update_slot(
    db: Session,
    space: Space,
    slot: SpaceSlot,
    data: SpaceSlotUpdate,
    *,
    apply_to: str = "one",
) -> SpaceSlot:
    """Edit a slot; with ``apply_to="upcoming"``, apply the changed fields to
    every slot in its series dated on/after it. ``slot_date`` only ever moves
    the edited slot (a series keeps its generated dates). Past occurrences are
    editable (no past guard) — admins may need to fix records; capacity lowering
    never evicts existing bookings (documented behaviour)."""
    payload = data.model_dump(exclude_unset=True)
    payload.pop("all_day", None)
    if data.all_day:
        payload["start_time"] = space.open_time
        payload["end_time"] = space.close_time

    if apply_to == "upcoming" and slot.series_id is not None:
        targets = (
            db.query(SpaceSlot)
            .filter(
                SpaceSlot.series_id == slot.series_id,
                SpaceSlot.slot_date >= slot.slot_date,
            )
            .order_by(SpaceSlot.slot_date)
            .all()
        )
        payload.pop("slot_date", None)
    else:
        targets = [slot]

    exclude = {t.id for t in targets}
    for target in targets:
        slot_date = (
            payload.get("slot_date", target.slot_date)
            if target.id == slot.id
            else target.slot_date
        )
        start_time = payload.get("start_time", target.start_time)
        end_time = payload.get("end_time", target.end_time)
        if end_time <= start_time:
            raise SlotOutsideOpeningHours("end_time must be after start_time")
        _validate_slot_on_date(
            db,
            space,
            slot_date=slot_date,
            start_time=start_time,
            end_time=end_time,
            exclude_slot_ids=exclude,
        )

    for target in targets:
        for key, value in payload.items():
            if key == "slot_date" and target.id != slot.id:
                continue
            setattr(target, key, value)
    return slot


def delete_slot(
    db: Session,
    slot: SpaceSlot,
    *,
    force: bool = False,
    notifier: BookingNotifier | None = None,
) -> list[Booking]:
    """Destructively delete a slot (bookings cascade). Without force, refuses
    when members hold active bookings on it (today or future); with force,
    every affected member is notified before the rows are gone."""
    notifier = notifier or NullBookingNotifier()
    affected = _affected_active_bookings(db, [slot.id])
    if affected and not force:
        raise HasActiveBookings(len({b.member_id for b in affected}))
    space = get_space(db, slot.space_id)
    for b in affected:
        notifier.send_admin_cancellation(
            _notification(db, b, slot, space, b.member)
        )
    db.delete(slot)
    return affected


# --- Counts ---------------------------------------------------------------


def _count(db: Session, slot_id: int, status: str) -> int:
    return (
        db.query(func.count(Booking.id))
        .filter(
            Booking.space_slot_id == slot_id,
            Booking.status == status,
        )
        .scalar()
        or 0
    )


def _member_active_booking(
    db: Session, slot_id: int, member_id: int
) -> Booking | None:
    return (
        db.query(Booking)
        .filter(
            Booking.space_slot_id == slot_id,
            Booking.member_id == member_id,
            Booking.status.in_(ACTIVE_STATUSES),
        )
        .first()
    )


def _counts_by_slot(db: Session, slot_ids: list[int]) -> dict[tuple[int, str], int]:
    """Booked / waitlisted counts for many slots in one query, keyed by
    ``(slot_id, status)``. The week view is the member-facing calendar that
    everyone opens at once when booking opens; a query per slot per count made
    it two round trips per cell."""
    if not slot_ids:
        return {}
    rows = (
        db.query(Booking.space_slot_id, Booking.status, func.count(Booking.id))
        .filter(
            Booking.space_slot_id.in_(slot_ids),
            Booking.status.in_(ACTIVE_STATUSES),
        )
        .group_by(Booking.space_slot_id, Booking.status)
        .all()
    )
    return {(slot_id, status): count for slot_id, status, count in rows}


def _member_statuses_by_slot(
    db: Session, slot_ids: list[int], member_id: int
) -> dict[int, str]:
    """The member's active booking status per slot, for the slots they hold."""
    if not slot_ids:
        return {}
    rows = (
        db.query(Booking.space_slot_id, Booking.status)
        .filter(
            Booking.space_slot_id.in_(slot_ids),
            Booking.member_id == member_id,
            Booking.status.in_(ACTIVE_STATUSES),
        )
        .all()
    )
    return {slot_id: status for slot_id, status in rows}


# --- Availability ---------------------------------------------------------


def space_week_availability(
    db: Session, space: Space, week_start: date, member_id: int | None
) -> list[dict]:
    """One cell per active slot dated within the week starting at ``week_start``
    (which should be a Monday)."""
    tz = _tz(db)
    now_local = datetime.now(tz)
    today = now_local.date()
    window_end = today + timedelta(days=_window_days(db))

    slots = (
        db.query(SpaceSlot)
        .filter(
            SpaceSlot.space_id == space.id,
            SpaceSlot.is_active.is_(True),
            SpaceSlot.slot_date >= week_start,
            SpaceSlot.slot_date < week_start + timedelta(days=7),
        )
        .order_by(SpaceSlot.slot_date, SpaceSlot.start_time)
        .all()
    )
    slot_ids = [slot.id for slot in slots]
    counts = _counts_by_slot(db, slot_ids)
    my_statuses = (
        _member_statuses_by_slot(db, slot_ids, member_id) if member_id is not None else {}
    )

    cells: list[dict] = []
    for slot in slots:
        on = slot.slot_date
        booked = counts.get((slot.id, BookingStatus.BOOKED), 0)
        waitlisted = counts.get((slot.id, BookingStatus.WAITLISTED), 0)
        my_status = my_statuses.get(slot.id, "none")

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
                "weekday": on.weekday(),
                "start_time": slot.start_time,
                "end_time": slot.end_time,
                "capacity": slot.capacity,
                "price": booking_price(space, slot),
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
        date_str=slot.slot_date.strftime("%d/%m/%Y"),
        time_str=time_str,
        locale=_locale(db),
        **extra,
    )


def create_booking(
    db: Session,
    member: Member,
    space_slot_id: int,
    *,
    notifier: BookingNotifier | None = None,
) -> Booking:
    """Book a slot, or waitlist it when full. Returns the new booking."""
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

    eligibility = check_space_eligibility(space, member)
    if not eligibility.eligible:
        raise NotEligible(eligibility.reason, eligibility.message)

    tz = _tz(db)
    now_local = datetime.now(tz)
    slot_start = datetime.combine(slot.slot_date, slot.start_time, tzinfo=tz)
    if slot_start <= now_local:
        raise BookingInPast("Slot has already started")
    if slot.slot_date > now_local.date() + timedelta(days=_window_days(db)):
        raise BookingWindowExceeded("Beyond the booking window")

    if _member_active_booking(db, slot.id, member.id) is not None:
        raise DuplicateBooking("Member already holds this slot")

    booked = _count(db, slot.id, BookingStatus.BOOKED)
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
        status=status,
        waitlisted_at=waitlisted_at,
    )
    db.add(booking)
    db.flush()

    if status == BookingStatus.BOOKED:
        ensure_booking_receipt(db, booking, slot, space)
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
        position = _count(db, slot.id, BookingStatus.WAITLISTED)
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
        slot_start = datetime.combine(slot.slot_date, slot.start_time, tzinfo=tz)
        deadline = slot_start - timedelta(hours=_deadline_hours(db))
        if now_local >= deadline:
            raise CancellationTooLate("Past the cancellation deadline")

    was_booked = booking.status == BookingStatus.BOOKED
    booking.status = BookingStatus.CANCELLED
    booking.cancelled_at = now_local
    booking.cancelled_by_user_id = cancelled_by_user_id
    db.flush()

    # Money follows the seat: whatever is still unpaid is voided here, and a
    # paid receipt is left standing — the club settles that one offline.
    void_booking_receipts(db, booking)

    if is_admin:
        # The member didn't cancel this themselves — tell them.
        space = get_space(db, slot.space_id)
        member = (
            db.query(Member)
            .options(joinedload(Member.person))
            .filter(Member.id == booking.member_id)
            .first()
        )
        if member is not None and space is not None:
            notifier.send_admin_cancellation(
                _notification(db, booking, slot, space, member)
            )

    if was_booked:
        booked = _count(db, slot.id, BookingStatus.BOOKED)
        if booked < slot.capacity:
            _promote_next(db, slot, notifier)
    return booking


def _promote_next(
    db: Session, slot: SpaceSlot, notifier: BookingNotifier
) -> Booking | None:
    """Promote the earliest waitlisted member who may still hold the slot.

    Promotion is a confirmation path, so it re-checks eligibility rather than
    trusting the check that ran when the member joined the waitlist: a tier can
    be changed or cleared while a member waits, and promoting them would hand
    them a seat in a space they are no longer allowed to use. An ineligible
    member is skipped and keeps their place on the waitlist — the seat goes to
    the next eligible one, and nobody is silently cancelled for an
    administrative change they did not make.
    """
    space = get_space(db, slot.space_id)
    candidates = (
        db.query(Booking)
        .filter(
            Booking.space_slot_id == slot.id,
            Booking.status == BookingStatus.WAITLISTED,
        )
        .order_by(Booking.waitlisted_at.asc(), Booking.id.asc())
        .all()
    )
    for candidate in candidates:
        member = (
            db.query(Member)
            .options(joinedload(Member.person))
            .filter(Member.id == candidate.member_id)
            .first()
        )
        if member is None:
            continue
        if space is not None and not check_space_eligibility(space, member).eligible:
            continue
        candidate.status = BookingStatus.BOOKED
        candidate.waitlisted_at = None
        db.flush()
        if space is not None:
            # Promotion confirms a seat, so it bills like any other confirmation
            # path — the one that is easiest to forget.
            ensure_booking_receipt(db, candidate, slot, space)
            notifier.send_promoted(
                _notification(db, candidate, slot, space, member)
            )
        return candidate
    return None


# --- Reads ----------------------------------------------------------------


def my_bookings(db: Session, member_id: int, *, scope: str) -> list[dict]:
    """A member's non-cancelled bookings, denormalized, upcoming or past."""
    tz = _tz(db)
    today = datetime.now(tz).date()

    query = (
        db.query(Booking)
        .join(SpaceSlot, Booking.space_slot_id == SpaceSlot.id)
        .options(joinedload(Booking.slot).joinedload(SpaceSlot.space))
        .filter(
            Booking.member_id == member_id,
            Booking.status.in_(ACTIVE_STATUSES),
        )
    )
    if scope == "past":
        query = query.filter(SpaceSlot.slot_date < today).order_by(
            SpaceSlot.slot_date.desc()
        )
    else:
        query = query.filter(SpaceSlot.slot_date >= today).order_by(
            SpaceSlot.slot_date.asc()
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
                "slot_date": slot.slot_date,
                "start_time": slot.start_time,
                "end_time": slot.end_time,
                "status": b.status,
                "capacity": slot.capacity,
                "booked_count": _count(db, slot.id, BookingStatus.BOOKED),
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
        query = query.filter(SpaceSlot.slot_date == on)
    if status:
        query = query.filter(Booking.status == status)
    return query.order_by(SpaceSlot.slot_date.desc(), Booking.id.desc())


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
