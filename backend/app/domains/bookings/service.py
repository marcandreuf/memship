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
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Query, Session, joinedload, selectinload

from app.core.clock import org_timezone
from app.domains.activities.models import PAYMENT_FLOW_PAY_TO_CONFIRM
from app.domains.billing.payment_instructions import unusable_methods
from app.domains.billing.seats import SeatError, refuse_paid_space_without_notices
from app.domains.bookings.billing import (
    booking_description,
    booking_price,
    ensure_booking_receipt,
    has_paid_receipt,
    void_booking_receipts,
)
from app.domains.bookings.payment import (
    auto_cancel_hours,
    auto_promotion_min,
    booking_payment_details,
    cutoff_minutes,
    min_hold,
    needs_payment,
    payment_deadline,
    seat_offer_details,
)
from app.domains.bookings.eligibility import check_space_eligibility
from app.domains.bookings.models import Booking, Space, SpaceSlot
from app.domains.bookings.notifications import (
    BookingNotification,
    BookingNotifier,
    EmailBookingNotifier,
    NullBookingNotifier,
)
from app.domains.bookings.rules import int_rule
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

ACTIVE_STATUSES = (BookingStatus.BOOKED, BookingStatus.PENDING, BookingStatus.WAITLISTED)

# Statuses that hold a seat. A pending booking holds one while it waits to be
# paid, so every capacity count reads this one rule (#603).
OCCUPYING_STATUSES = (BookingStatus.BOOKED, BookingStatus.PENDING)


def occupies_seat(status: str | None) -> bool:
    return status in OCCUPYING_STATUSES


# --- Errors ---------------------------------------------------------------


class BookingError(Exception):
    """Base class for booking domain errors.

    ``dates`` names the occurrences a series-wide check failed on, so the API
    can report them beside the code; it is empty for a single-slot error.
    """

    dates: list[date] = []
    #: Further fields the API adds to the error beside its code.
    fields: dict = {}


class SpaceNotFound(BookingError):
    pass


class SlotNotFound(BookingError):
    pass


class InvalidTimeRange(BookingError):
    """An end time that is not after its start time."""


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


class BookingHoldTooShort(BookingError):
    """A paid booking would have less time to pay than the club's shortest hold.

    Refused rather than created already doomed. Carries the deadline it would
    have had and the club's cut-off, so the member is told why.
    """

    def __init__(self, pay_by: datetime, cutoff: int):
        super().__init__("Too close to the slot to hold it until paid")
        self.fields = {"pay_by": pay_by.isoformat(), "cutoff_minutes": cutoff}


class SeatReceiptFailed(BookingError):
    """The receipt of a booking held until paid could not be raised, so the
    booking cannot be held: nobody could pay it."""


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


class NotPending(BookingError):
    """The action is only for a booking waiting for its payment."""


class NotCancellable(BookingError):
    pass


class HasActiveBookings(BookingError):
    """Deleting would destroy members' active bookings; pass force to proceed."""

    def __init__(self, affected_members: int):
        super().__init__(str(affected_members))
        self.affected_members = affected_members


class HasPaidBookings(BookingError):
    """Deleting would erase bookings that carry money: paid ones whose slot is
    still to come, and cancelled ones the club still owes back. Deleting
    cascades the bookings away, and their ``refund_status`` with them. The club
    cancels them first, which records what is owed, or deactivates instead
    (#603).
    """

    def __init__(self, count: int):
        super().__init__(f"{count} booking(s) carry a payment")
        self.fields = {"count": count}


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


def _window_days(db: Session) -> int:
    return int_rule(_features(db), "booking_window_days")


def _deadline_hours(db: Session) -> int:
    return int_rule(_features(db), "booking_cancellation_deadline_hours")


def _self_cancel_deadline(slot: SpaceSlot, tz, deadline_hours: int) -> datetime:
    """The last moment a member may cancel their own booking on ``slot``."""
    slot_start = datetime.combine(slot.slot_date, slot.start_time, tzinfo=tz)
    return slot_start - timedelta(hours=deadline_hours)


def _waitlist_enabled(db: Session) -> bool:
    return bool(_features(db).get("booking_waitlist_enabled", True))


# --- Paid spaces (#603) ----------------------------------------------------

#: The fields whose change can make a space start charging, or charge in ways
#: it cannot take.
_PAYMENT_FIELDS = frozenset({"price", "payment_flow", "payment_methods", "is_active"})


class SpacePaymentMethodsRequired(BookingError):
    """A space that charges must accept at least one way to pay."""


class PaymentMethodsUnavailable(BookingError):
    """The space accepts methods the club cannot take today."""

    def __init__(self, methods: list[str]):
        super().__init__("Payment methods not available at this club: " + ", ".join(methods))
        self.fields = {"methods": methods}


class SpacePaymentNeedsEmails(BookingError):
    """A space that charges releases unpaid bookings; its holders must be told."""

    def __init__(self, templates: list[str]):
        super().__init__("A paid space needs these emails switched on first: " + ", ".join(templates))
        self.fields = {"templates": templates}


def _charges(db: Session, space: Space) -> bool:
    """Whether a booking of the space can be held until paid: it is
    pay-to-confirm and charges, by its own price or a slot's."""
    if not needs_payment(space, Decimal("1")):
        return False
    if space.price is not None and space.price > 0:
        return True
    if space.id is None:
        return False
    db.flush()
    return (
        db.query(SpaceSlot.id)
        .filter(SpaceSlot.space_id == space.id, SpaceSlot.price > 0)
        .first()
        is not None
    )


def _refuse_unpayable_space(db: Session, space: Space) -> None:
    """A space that charges must be payable, exactly as a paid activity must be
    to publish (#591): at least one method, each one the club can take, and the
    mails that tell a member their booking is held, about to go, and gone."""
    if not _charges(db, space):
        return
    if not space.payment_methods:
        raise SpacePaymentMethodsRequired(
            "A paid space must accept at least one payment method"
        )
    unusable = unusable_methods(db, list(space.payment_methods))
    if unusable:
        raise PaymentMethodsUnavailable(unusable)
    try:
        refuse_paid_space_without_notices(db)
    except SeatError as exc:
        raise SpacePaymentNeedsEmails(exc.detail["templates"]) from exc


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
        payment_flow=PAYMENT_FLOW_PAY_TO_CONFIRM,
        payment_methods=list(data.payment_methods),
        auto_cancel_enabled=data.auto_cancel_enabled,
        auto_cancel_hours=data.auto_cancel_hours,
    )
    db.add(space)
    _refuse_unpayable_space(db, space)
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
    auto_cancel_was_on = auto_cancel_hours(db, space) is not None
    for key, value in payload.items():
        setattr(space, key, value)
    if space.close_time <= space.open_time:
        raise InvalidTimeRange("close_time must be after open_time")
    if payload.keys() & _PAYMENT_FIELDS:
        _refuse_unpayable_space(db, space)
    if not auto_cancel_was_on and auto_cancel_hours(db, space) is not None:
        # Its pending bookings had only the cut-off; they now have less time.
        shorten_pending_deadlines(db, [space], notifier=notifier)

    if payload.keys() & {"open_time", "close_time"}:
        stranded = _slots_outside_hours(db, space)
        if stranded:
            affected = _affected_active_bookings(db, [s.id for s in stranded])
            if not force:
                raise SlotsOutsideHours(
                    len(stranded), len({b.party_id for b in affected})
                )
            for slot in stranded:
                delete_slot(db, slot, force=True, notifier=notifier)
    return space


def _slots_outside_hours(db: Session, space: Space) -> list[SpaceSlot]:
    """Upcoming active slots that start before the space opens or end after it
    closes. Past slots are history and stay as they are."""
    today = datetime.now(org_timezone(db)).date()
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
    today = datetime.now(org_timezone(db)).date()
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


def _refuse_deleting_paid_bookings(db: Session, slot_ids: list[int]) -> None:
    """Refuse to delete slots whose bookings carry money: one still to come that
    was paid for, or a cancelled one whose refund is due. Checked before the
    active-bookings confirmation, so the club is not asked to confirm a delete
    that would be refused anyway."""
    if not slot_ids:
        return
    from app.domains.billing.models import Receipt

    db.flush()

    today = datetime.now(org_timezone(db)).date()
    paid = (
        db.query(Receipt.id)
        .filter(
            Receipt.booking_id == Booking.id,
            Receipt.is_active.is_(True),
            Receipt.document_type == "invoice",
            Receipt.status == "paid",
        )
        .exists()
    )
    count = (
        db.query(func.count(Booking.id))
        .join(SpaceSlot, Booking.space_slot_id == SpaceSlot.id)
        .filter(
            Booking.space_slot_id.in_(slot_ids),
            (Booking.refund_status == "due")
            | (
                Booking.status.in_(OCCUPYING_STATUSES)
                & (SpaceSlot.slot_date >= today)
                & paid
            ),
        )
        .scalar()
    )
    if count:
        raise HasPaidBookings(count)


def delete_space(
    db: Session,
    space: Space,
    *,
    force: bool = False,
    notifier: BookingNotifier | None = None,
) -> list[Booking]:
    """Destructively delete a space (slots + bookings cascade). Without force,
    refuses when members hold active future bookings; with force, every
    affected member is notified and their unpaid receipts voided before the rows
    are gone, as cancelling each booking would. Deactivation via update is the
    non-destructive default path. Never with bookings that carry money
    (``HasPaidBookings``), forced or not."""
    notifier = notifier or NullBookingNotifier()
    slot_ids = [s.id for s in space.slots]
    _refuse_deleting_paid_bookings(db, slot_ids)
    affected = _affected_active_bookings(db, slot_ids)
    if affected and not force:
        raise HasActiveBookings(len({b.party_id for b in affected}))
    for b in affected:
        void_booking_receipts(db, b)
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
    tz = org_timezone(db)
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
    failed: list[date] = []
    for d in dates:
        try:
            _past_guard(db, d, start_time)
            _validate_slot_on_date(
                db, space, slot_date=d, start_time=start_time, end_time=end_time
            )
        except BookingError as exc:
            errors.append(str(exc))
            failed.append(d)
    if errors:
        message = "; ".join(errors)
        if any("overlaps" in e for e in errors):
            error: BookingError = SlotOverlap(message)
        elif any("opening hours" in e for e in errors):
            error = SlotOutsideOpeningHours(message)
        else:
            error = SlotInPast(message)
        error.dates = failed
        raise error

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
    if data.price:
        _refuse_unpayable_space(db, space)
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
            raise InvalidTimeRange("end_time must be after start_time")
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
    if payload.get("price"):
        _refuse_unpayable_space(db, space)
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
    every affected member is notified and their unpaid receipts voided before
    the rows are gone, as cancelling each booking would. Never with bookings
    that carry money (``HasPaidBookings``), forced or not."""
    notifier = notifier or NullBookingNotifier()
    _refuse_deleting_paid_bookings(db, [slot.id])
    affected = _affected_active_bookings(db, [slot.id])
    if affected and not force:
        raise HasActiveBookings(len({b.party_id for b in affected}))
    space = get_space(db, slot.space_id)
    for b in affected:
        void_booking_receipts(db, b)
        notifier.send_admin_cancellation(
            _notification(db, b, slot, space, b.member)
        )
    db.delete(slot)
    return affected


# --- Counts ---------------------------------------------------------------


def _occupied(db: Session, slot_id: int) -> int:
    """How many seats of the slot are held, paid or waiting to be."""
    return (
        db.query(func.count(Booking.id))
        .filter(
            Booking.space_slot_id == slot_id,
            Booking.status.in_(OCCUPYING_STATUSES),
        )
        .scalar()
        or 0
    )


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
    db: Session, slot_id: int, party_id: int
) -> Booking | None:
    return (
        db.query(Booking)
        .filter(
            Booking.space_slot_id == slot_id,
            Booking.party_id == party_id,
            Booking.status.in_(ACTIVE_STATUSES),
        )
        .first()
    )


def _counts_by_slot(db: Session, slot_ids: list[int]) -> dict[tuple[int, str], int]:
    """Booked / pending / waitlisted counts for many slots in one query, keyed by
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
    db: Session, slot_ids: list[int], party_id: int
) -> dict[int, str]:
    """The member's active booking status per slot, for the slots they hold."""
    if not slot_ids:
        return {}
    rows = (
        db.query(Booking.space_slot_id, Booking.status)
        .filter(
            Booking.space_slot_id.in_(slot_ids),
            Booking.party_id == party_id,
            Booking.status.in_(ACTIVE_STATUSES),
        )
        .all()
    )
    return {slot_id: status for slot_id, status in rows}


# --- Availability ---------------------------------------------------------


def space_week_availability(
    db: Session, space: Space, week_start: date, party_id: int | None
) -> list[dict]:
    """One cell per active slot dated within the week starting at ``week_start``
    (which should be a Monday)."""
    tz = org_timezone(db)
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
    hold = min_hold(db)
    my_statuses = (
        _member_statuses_by_slot(db, slot_ids, party_id) if party_id is not None else {}
    )

    cells: list[dict] = []
    for slot in slots:
        on = slot.slot_date
        booked = sum(counts.get((slot.id, s), 0) for s in OCCUPYING_STATUSES)
        waitlisted = counts.get((slot.id, BookingStatus.WAITLISTED), 0)
        my_status = my_statuses.get(slot.id, "none")

        price = booking_price(space, slot)
        slot_start = datetime.combine(on, slot.start_time, tzinfo=tz)
        # When a paid booking taken now would have to be paid by. Shown before
        # booking, so the member knows the hold is real and how long it lasts.
        pay_by = (
            payment_deadline(db, space, slot, now_local)
            if slot_start > now_local and needs_payment(space, price)
            else None
        )
        if slot_start <= now_local:
            cell_state = "past"
        elif on > window_end:
            cell_state = "out_of_window"
        elif booked >= slot.capacity:
            cell_state = "full"
        elif pay_by is not None and pay_by - now_local < hold:
            # Too close to the start to be held until paid: a booking would be
            # refused, so the calendar does not offer it.
            cell_state = "too_late"
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
                "price": price,
                "pay_by": pay_by,
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
    """Book a slot, or waitlist it when full. Returns the booking.

    A member already on the slot's waiting list who books a seat that has
    freed takes it with that same row.
    """
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

    tz = org_timezone(db)
    now_local = datetime.now(tz)
    slot_start = datetime.combine(slot.slot_date, slot.start_time, tzinfo=tz)
    if slot_start <= now_local:
        raise BookingInPast("Slot has already started")
    if slot.slot_date > now_local.date() + timedelta(days=_window_days(db)):
        raise BookingWindowExceeded("Beyond the booking window")

    # A waitlister booking a seat that has freed takes it with their own row:
    # one active row per member and slot, and their place in the queue is moot
    # once they hold the seat (#603). Anyone else already on the slot holds it.
    waiting = _member_active_booking(db, slot.id, member.party_id)
    if waiting is not None and waiting.status != BookingStatus.WAITLISTED:
        raise DuplicateBooking("Member already holds this slot")

    now = datetime.now(timezone.utc)
    payment_due_at = None
    if _occupied(db, slot.id) < slot.capacity:
        status = BookingStatus.BOOKED
        waitlisted_at = None
        if needs_payment(space, booking_price(space, slot)):
            payment_due_at = payment_deadline(db, space, slot, now)
            if payment_due_at - now < min_hold(db):
                raise BookingHoldTooShort(payment_due_at, cutoff_minutes(db))
            status = BookingStatus.PENDING
    elif waiting is not None:
        raise DuplicateBooking("Member is already on the waitlist for this slot")
    elif _waitlist_enabled(db):
        status = BookingStatus.WAITLISTED
        waitlisted_at = now_local
    else:
        raise SlotFull("Slot is full and the waitlist is disabled")

    booking = waiting or Booking(space_slot_id=slot.id, party_id=member.party_id)
    booking.status = status
    booking.waitlisted_at = waitlisted_at
    booking.payment_due_at = payment_due_at
    booking.pending_since = now if payment_due_at else None
    db.add(booking)
    db.flush()

    if status == BookingStatus.PENDING:
        receipt = _bill_pending(db, booking, slot, space)
        notifier.send_pending_payment(
            _notification(
                db,
                booking,
                slot,
                space,
                member,
                payment=booking_payment_details(
                    db, booking, space, receipt, _locale(db)
                ),
            )
        )
    elif status == BookingStatus.BOOKED:
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


def _bill_pending(db: Session, booking: Booking, slot: SpaceSlot, space: Space):
    """The receipt of a booking held until paid, which it cannot be held without."""
    try:
        return ensure_booking_receipt(db, booking, slot, space)
    except Exception as exc:
        raise SeatReceiptFailed(
            "The receipt for this booking could not be raised, so it cannot be held"
        ) from exc


def _self_cancel_refusal(db: Session, booking: Booking, slot: SpaceSlot) -> str | None:
    """Why the member may not cancel this booking themselves, or None.

    A pending booking may be released until its payment deadline, whatever the
    club's cancellation notice: nothing has been paid, and a seat given back
    early is one the club can still fill (#603).
    """
    tz = org_timezone(db)
    now_local = datetime.now(tz)
    if booking.status == BookingStatus.PENDING:
        if booking.payment_due_at is not None and now_local >= booking.payment_due_at:
            return "Past the payment deadline"
        return None
    if now_local >= _self_cancel_deadline(slot, tz, _deadline_hours(db)):
        return "Past the cancellation deadline"
    return None


def _member_of(db: Session, booking: Booking) -> Member | None:
    return (
        db.query(Member)
        .options(joinedload(Member.person))
        .filter(Member.party_id == booking.party_id)
        .order_by(Member.is_active.desc(), Member.id.desc())
        .first()
    )


def release_booking(
    db: Session,
    booking: Booking,
    *,
    cancelled_by_user_id: int | None = None,
    keep_payment: bool = False,
) -> bool:
    """The one way a booking stops holding a seat, and the receipt side of it.

    Whatever is still unpaid is voided. A paid receipt stays, and a booking that
    was paid for is owed back (``refund_status = due``) unless the club keeps
    the payment. Returns whether the booking held a seat, so the caller knows
    one has freed.
    """
    held = occupies_seat(booking.status)
    booking.status = BookingStatus.CANCELLED
    booking.cancelled_at = datetime.now(timezone.utc)
    booking.cancelled_by_user_id = cancelled_by_user_id
    booking.payment_due_at = None
    booking.payment_reminder_sent_at = None
    db.flush()

    void_booking_receipts(db, booking)
    if has_paid_receipt(db, booking):
        booking.refund_status = "none" if keep_payment else "due"
    return held


def cancel_booking(
    db: Session,
    booking: Booking,
    *,
    cancelled_by_user_id: int,
    is_admin: bool,
    notifier: BookingNotifier | None = None,
    keep_payment: bool = False,
) -> Booking:
    """Cancel a booking; promote the earliest waitlisted member if a seat frees.

    ``keep_payment`` is the club's choice, on cancelling a paid booking, not to
    return the money.
    """
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

    if not is_admin:
        refusal = _self_cancel_refusal(db, booking, slot)
        if refusal:
            raise CancellationTooLate(refusal)

    held = release_booking(
        db,
        booking,
        cancelled_by_user_id=cancelled_by_user_id,
        keep_payment=keep_payment and is_admin,
    )

    if is_admin:
        # The member didn't cancel this themselves — tell them, and whether
        # what they paid is coming back.
        space = get_space(db, slot.space_id)
        member = _member_of(db, booking)
        if member is not None and space is not None:
            notifier.send_admin_cancellation(
                _notification(
                    db,
                    booking,
                    slot,
                    space,
                    member,
                    refund_due=booking.refund_status == "due",
                )
            )

    if held and _occupied(db, slot.id) < slot.capacity:
        _on_seat_freed(db, slot, notifier)
    return booking


def confirm_pending_booking(
    db: Session, booking_id: int, *, notifier: BookingNotifier | None = None
) -> None:
    """Book a pending booking whose receipt has just been paid.

    Only a ``pending`` one: a ``legacy`` space never has any, and a booking
    already booked, waitlisted or cancelled is not this function's to change.
    """
    notifier = notifier or NullBookingNotifier()
    booking = get_booking(db, booking_id)
    if booking is None or booking.status != BookingStatus.PENDING:
        return
    _book_pending(db, booking, notifier)


def confirm_booking_without_payment(
    db: Session,
    booking: Booking,
    user_id: int,
    *,
    notifier: BookingNotifier | None = None,
) -> Booking:
    """Book a pending booking and waive its payment, on the club's word.

    The receipt is cancelled rather than left standing, so a booked member never
    carries a live receipt the dunning run would chase. Recorded in the audit
    log, since it gives up money the club was owed.
    """
    if booking.status != BookingStatus.PENDING:
        raise NotPending("Only a pending booking can be confirmed without payment")

    from app.domains.audit.models import AuditLog

    void_booking_receipts(db, booking)
    db.add(
        AuditLog(
            table_name="bookings",
            record_id=booking.id,
            action="update",
            user_id=user_id,
            old_values={"status": "pending"},
            new_values={"status": "booked", "reason": "payment_waived"},
            changed_fields=["status"],
        )
    )
    _book_pending(db, booking, notifier or NullBookingNotifier())
    return booking


def _book_pending(db: Session, booking: Booking, notifier: BookingNotifier) -> None:
    booking.status = BookingStatus.BOOKED
    booking.payment_due_at = None
    booking.payment_reminder_sent_at = None
    db.flush()
    slot = booking.slot
    member = _member_of(db, booking)
    if member is not None:
        notifier.send_confirmation(
            _notification(
                db,
                booking,
                slot,
                slot.space,
                member,
                cancellation_deadline_hours=_deadline_hours(db),
            )
        )


def _on_seat_freed(db: Session, slot: SpaceSlot, notifier: BookingNotifier) -> None:
    """A seat of ``slot`` has just freed: offer it to the waiting list.

    A seat that costs nothing upfront goes to the next waitlister, as always. A
    paid one in a pay-to-confirm space depends on the hold a booking would get
    now (#603):

    - at least the club's auto-promotion threshold: the next waitlister is
      promoted to ``pending``, with its deadline;
    - at least the shortest hold, but under that threshold: nobody is promoted,
      since a member promoted unawares could sit on the seat until it was too
      late for anyone. Every waitlister is told instead, and the first to book
      it takes it;
    - under the shortest hold: the seat is given up. A booking would be refused.
    """
    space = get_space(db, slot.space_id)
    if space is None:
        return
    if not needs_payment(space, booking_price(space, slot)):
        _promote_next(db, slot, space, notifier)
        return
    now = datetime.now(timezone.utc)
    due = payment_deadline(db, space, slot, now)
    if due - now >= auto_promotion_min(db):
        _promote_next(db, slot, space, notifier, payment_due_at=due, now=now)
    elif due - now >= min_hold(db):
        _offer_freed_seat(db, slot, space, due, notifier)


def _eligible_waitlisters(
    db: Session, slot: SpaceSlot, space: Space
) -> list[tuple[Booking, Member]]:
    """The slot's waitlisters, first come first, who may still hold it.

    Re-checked rather than trusted from when they joined: a tier can be changed
    or cleared while a member waits, and handing them a seat in a space they are
    no longer allowed to use would be wrong. An ineligible member keeps their
    place on the waitlist, and nobody is silently cancelled for an
    administrative change they did not make.
    """
    candidates = (
        db.query(Booking)
        .filter(
            Booking.space_slot_id == slot.id,
            Booking.status == BookingStatus.WAITLISTED,
        )
        .order_by(Booking.waitlisted_at.asc(), Booking.id.asc())
        .all()
    )
    eligible = []
    for candidate in candidates:
        member = _member_of(db, candidate)
        if member is not None and check_space_eligibility(space, member).eligible:
            eligible.append((candidate, member))
    return eligible


def _promote_next(
    db: Session,
    slot: SpaceSlot,
    space: Space,
    notifier: BookingNotifier,
    *,
    payment_due_at: datetime | None = None,
    now: datetime | None = None,
) -> Booking | None:
    """Give the freed seat to the earliest eligible waitlister.

    With a ``payment_due_at`` the seat is held until paid, so the promotee is
    ``pending`` and told how and by when to pay; without one they are booked.
    Either way promotion bills like any other path that gives a seat — the one
    that is easiest to forget.
    """
    eligible = _eligible_waitlisters(db, slot, space)
    if not eligible:
        return None
    candidate, member = eligible[0]
    candidate.waitlisted_at = None
    payment = None
    if payment_due_at is not None:
        candidate.status = BookingStatus.PENDING
        candidate.payment_due_at = payment_due_at
        candidate.pending_since = now
        candidate.payment_reminder_sent_at = None
        db.flush()
        receipt = _bill_pending(db, candidate, slot, space)
        payment = booking_payment_details(db, candidate, space, receipt, _locale(db))
    else:
        candidate.status = BookingStatus.BOOKED
        db.flush()
        ensure_booking_receipt(db, candidate, slot, space)
    notifier.send_promoted(
        _notification(db, candidate, slot, space, member, payment=payment)
    )
    return candidate


def _offer_freed_seat(
    db: Session, slot: SpaceSlot, space: Space, pay_by: datetime, notifier: BookingNotifier
) -> None:
    """Tell every eligible waitlister a seat is free to book and pay by ``pay_by``.

    They all stay on the waiting list; the first to book takes it.
    """
    offer = seat_offer_details(db, space, slot, pay_by, _locale(db))
    for candidate, member in _eligible_waitlisters(db, slot, space):
        notifier.send_seat_available(
            _notification(db, candidate, slot, space, member, payment=offer)
        )


# --- Reads ----------------------------------------------------------------


def my_bookings(db: Session, party_id: int, *, scope: str) -> list[dict]:
    """A member's non-cancelled bookings, denormalized, upcoming or past."""
    tz = org_timezone(db)
    now_local = datetime.now(tz)
    today = now_local.date()
    deadline_hours = _deadline_hours(db)

    query = (
        db.query(Booking)
        .join(SpaceSlot, Booking.space_slot_id == SpaceSlot.id)
        .options(joinedload(Booking.slot).joinedload(SpaceSlot.space))
        .filter(
            Booking.party_id == party_id,
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
                "booked_count": _occupied(db, slot.id),
                "waitlist_position": position,
                # The same rule `cancel_booking` enforces, so the list only
                # offers a cancellation the server will accept.
                "can_cancel": (
                    now_local < b.payment_due_at
                    if b.status == BookingStatus.PENDING and b.payment_due_at
                    else now_local < _self_cancel_deadline(slot, tz, deadline_hours)
                ),
                "payment_due_at": b.payment_due_at,
                "receipt_id": receipt.id if (receipt := latest_receipt(b)) else None,
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
            selectinload(Booking.receipts),
        )
        .filter(SpaceSlot.space_id == space_id)
    )
    if on is not None:
        query = query.filter(SpaceSlot.slot_date == on)
    if status:
        query = query.filter(Booking.status == status)
    return query.order_by(SpaceSlot.slot_date.desc(), Booking.id.desc())


def latest_receipt(booking: Booking):
    """The booking's most recent invoice, whatever its state, or None."""
    invoices = [
        r for r in booking.receipts if r.is_active and r.document_type == "invoice"
    ]
    return max(invoices, key=lambda r: r.id) if invoices else None


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


STATS_WINDOW_DAYS = 30


def space_stats(db: Session) -> dict:
    """Dashboard aggregate over active slots in ``[today, today + 30 days)``.

    A rolling window rather than the calendar month, so the card always shows
    the month ahead instead of mostly-finished slots late in the month.
    ``active_spaces`` is not windowed.
    """
    today = datetime.now(org_timezone(db)).date()
    in_window = (
        SpaceSlot.is_active.is_(True),
        SpaceSlot.slot_date >= today,
        SpaceSlot.slot_date < today + timedelta(days=STATS_WINDOW_DAYS),
    )

    rows = (
        db.query(Booking.status, func.count(Booking.id))
        .join(SpaceSlot, Booking.space_slot_id == SpaceSlot.id)
        .filter(*in_window)
        .group_by(Booking.status)
        .all()
    )
    counts = {status: count for status, count in rows}

    slots, capacity = (
        db.query(func.count(SpaceSlot.id), func.coalesce(func.sum(SpaceSlot.capacity), 0))
        .filter(*in_window)
        .one()
    )
    active_spaces = db.query(func.count(Space.id)).filter(Space.is_active.is_(True)).scalar()

    booked = counts.get(BookingStatus.BOOKED, 0)
    pending = counts.get(BookingStatus.PENDING, 0)
    held = booked + pending
    return {
        "window_days": STATS_WINDOW_DAYS,
        "booked": booked,
        "pending": pending,
        "waitlisted": counts.get(BookingStatus.WAITLISTED, 0),
        "cancelled": counts.get(BookingStatus.CANCELLED, 0),
        "total": sum(counts.values()),
        "active_spaces": active_spaces,
        "slots": slots,
        "capacity": int(capacity),
        "occupancy_pct": round(held / capacity * 100, 1) if capacity else 0,
    }


# --- Payment deadlines (#603) ----------------------------------------------

#: How long before its deadline a pending booking's holder is warned, at most.
#: A shorter window is warned halfway through it instead. The activity rule.
DEADLINE_REMINDER_LEAD = timedelta(hours=24)


def expired_pending_bookings(db: Session, now: datetime) -> list[Booking]:
    """Pending bookings whose payment deadline has passed.

    Locked, skipping rows another transaction holds: a payment booking one at
    this moment wins, and the next sweep sees it booked.
    """
    return (
        db.query(Booking)
        .filter(
            Booking.status == BookingStatus.PENDING,
            Booking.payment_due_at.isnot(None),
            Booking.payment_due_at < now,
        )
        .order_by(Booking.payment_due_at, Booking.id)
        .with_for_update(skip_locked=True, of=Booking)
        .all()
    )


def expire_unpaid_booking(
    db: Session, booking: Booking, *, notifier: BookingNotifier | None = None
) -> None:
    """Release a booking left unpaid past its deadline, tell its holder, and
    offer the seat on, which may release it in turn later: the cascade."""
    notifier = notifier or NullBookingNotifier()
    slot = (
        db.query(SpaceSlot)
        .filter(SpaceSlot.id == booking.space_slot_id)
        .with_for_update()
        .first()
    )
    booking.cancelled_cause = "payment_expired"
    release_booking(db, booking)
    member = _member_of(db, booking)
    if member is not None:
        notifier.send_cancelled_unpaid(
            _notification(db, booking, slot, slot.space, member)
        )
    if _occupied(db, slot.id) < slot.capacity:
        _on_seat_freed(db, slot, notifier)


def remind_booking_deadlines(
    db: Session, now: datetime, *, notifier: BookingNotifier | None = None
) -> int:
    """Warn, once, each holder of a pending booking whose deadline is near.

    ``DEADLINE_REMINDER_LEAD`` before it, or halfway through a shorter window.
    The window runs from when the hold began, at booking or promotion, not
    from "now plus the auto-cancel hours": the cut-off before the slot can make
    it shorter than those. Returns how many were warned. Does not commit.
    """
    notifier = notifier or NullBookingNotifier()
    pending = (
        db.query(Booking)
        .filter(
            Booking.status == BookingStatus.PENDING,
            Booking.payment_due_at.isnot(None),
            Booking.payment_due_at > now,
            Booking.payment_reminder_sent_at.is_(None),
        )
        .all()
    )
    warned = 0
    for booking in pending:
        window = booking.payment_due_at - (booking.pending_since or booking.created_at)
        lead = min(DEADLINE_REMINDER_LEAD, window / 2)
        if now < booking.payment_due_at - lead:
            continue
        receipt = _live_receipt(db, booking)
        member = _member_of(db, booking)
        if receipt is None or member is None:
            continue
        booking.payment_reminder_sent_at = now
        slot = booking.slot
        notifier.send_deadline_reminder(
            _notification(
                db,
                booking,
                slot,
                slot.space,
                member,
                payment=booking_payment_details(
                    db, booking, slot.space, receipt, _locale(db)
                ),
            )
        )
        warned += 1
    db.flush()
    return warned


def _live_receipt(db: Session, booking: Booking):
    from app.domains.billing.models import Receipt

    return (
        db.query(Receipt)
        .filter(
            Receipt.booking_id == booking.id,
            Receipt.is_active.is_(True),
            Receipt.document_type == "invoice",
            Receipt.status.in_(("emitted", "overdue")),
        )
        .first()
    )


def shorten_pending_deadlines(
    db: Session,
    spaces: list[Space],
    *,
    notifier: BookingNotifier | None = None,
    now: datetime | None = None,
) -> int:
    """Bring forward the deadlines of pending bookings when auto-cancel comes on.

    A booking held while auto-cancel was off has only the cut-off before its
    slot. Each gets ``min(its deadline, now + hours)``, its receipt falls due by
    then, and its holder is sent the pending mail again saying the deadline has
    changed: a booking must not be released before its holder has been told it
    can be. One whose new hold would be under the club's shortest keeps its
    deadline. Returns how many were shortened. Does not commit.
    """
    from app.domains.billing.seats import receipt_due_date

    notifier = notifier or NullBookingNotifier()
    now = now or datetime.now(timezone.utc)
    floor = min_hold(db)
    db.flush()
    shortened = 0
    for space in spaces:
        hours = auto_cancel_hours(db, space)
        if hours is None:
            continue
        due_at = now + timedelta(hours=hours)
        if due_at - now < floor:
            continue
        bookings = (
            db.query(Booking)
            .join(SpaceSlot, Booking.space_slot_id == SpaceSlot.id)
            .filter(
                SpaceSlot.space_id == space.id,
                Booking.status == BookingStatus.PENDING,
                Booking.payment_due_at > due_at,
            )
            .all()
        )
        for booking in bookings:
            booking.payment_due_at = due_at
            booking.payment_reminder_sent_at = None
            receipt = _live_receipt(db, booking)
            if receipt is not None:
                receipt.due_date = receipt_due_date(db, due_at)
            member = _member_of(db, booking)
            if member is not None and receipt is not None:
                notifier.send_pending_payment(
                    _notification(
                        db,
                        booking,
                        booking.slot,
                        space,
                        member,
                        payment={
                            **booking_payment_details(
                                db, booking, space, receipt, _locale(db)
                            ),
                            "deadline_changed": True,
                        },
                    )
                )
            shortened += 1
    db.flush()
    return shortened


def settle_late_booking_payment(db: Session, receipt):
    """Give a booking back to a payment that arrived after it was released.

    Booked if the slot has not started and a seat is free, under the slot's
    lock; otherwise it stays cancelled and the money is owed back. A payment
    after the start cannot buy a slot that is already under way. Flagged for
    the club either way. Nothing is mailed to the member when no seat is given:
    "payment received, nothing more to do" would tell them they hold one.
    """
    from app.domains.billing.seats import LateSeat

    booking = get_booking(db, receipt.booking_id)
    slot = (
        db.query(SpaceSlot)
        .filter(SpaceSlot.id == booking.space_slot_id)
        .with_for_update()
        .first()
    )
    space = slot.space
    now = datetime.now(timezone.utc)
    booking.late_payment_at = now
    booking.late_payment_seen_at = None

    confirmed = occupies_seat(booking.status)
    if not confirmed:
        if (
            datetime.combine(slot.slot_date, slot.start_time, tzinfo=org_timezone(db)) > now
            and _occupied(db, slot.id) < slot.capacity
            and _member_active_booking(db, slot.id, booking.party_id) is None
        ):
            booking.status = BookingStatus.BOOKED
            booking.cancelled_at = None
            booking.cancelled_by_user_id = None
            booking.cancelled_cause = None
            booking.refund_status = "none"
            db.flush()
            member = _member_of(db, booking)
            if member is not None:
                notifier = EmailBookingNotifier(db)
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
            confirmed = True
        else:
            booking.refund_status = "due"
    db.flush()

    member = _member_of(db, booking)
    person = member.person if member else None
    return LateSeat(
        confirmed=confirmed,
        name=booking_description(space, slot),
        member_name=f"{person.first_name} {person.last_name}" if person else None,
    )
