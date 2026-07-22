"""Unit tests for the bookings service — capacity, waitlist, promotion, windows.

Uses the transactional ``db`` fixture; the service never commits, so these flush
and query back within the same transaction.
"""

from datetime import date, time, timedelta

import pytest

from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.bookings import service
from app.domains.bookings.models import Space, SpaceSlot
from app.domains.bookings.schemas import SpaceSlotCreate
from app.domains.members.models import Member
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


class RecordingNotifier:
    def __init__(self):
        self.calls = []

    def send_confirmation(self, note):
        self.calls.append(("confirmation", note))

    def send_waitlisted(self, note):
        self.calls.append(("waitlisted", note))

    def send_promoted(self, note):
        self.calls.append(("promoted", note))


def _org(db, **features):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(
            id=1, name="Club", locale="es", timezone="Europe/Madrid", currency="EUR"
        )
        db.add(org)
    org.features = {"bookings": True, **features}
    db.flush()
    return org


def _member(db, i=0):
    person = Person(first_name=f"M{i}", last_name="T", email=f"m{i}@t.com")
    db.add(person)
    db.flush()
    m = Member(person_id=person.id, status="active", is_active=True)
    db.add(m)
    db.flush()
    return m


def _user(db, i=0):
    person = Person(first_name="U", last_name="ser", email=f"u{i}@t.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id, email=f"u{i}@t.com",
        password_hash=hash_password("x"), role="admin", is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _space(db):
    s = Space(name="Court 1", open_time=time(8, 0), close_time=time(22, 0), is_active=True)
    db.add(s)
    db.flush()
    return s


def _slot(db, space, weekday, capacity=1):
    slot = SpaceSlot(
        space_id=space.id,
        weekday=weekday,
        start_time=time(10, 0),
        end_time=time(11, 0),
        capacity=capacity,
        is_active=True,
    )
    db.add(slot)
    db.flush()
    return slot


def _future(days=3):
    return date.today() + timedelta(days=days)


# --- Slot validation ------------------------------------------------------


def test_create_slot_rejects_outside_opening_hours(db):
    _org(db)
    space = _space(db)
    with pytest.raises(service.SlotOutsideOpeningHours):
        service.create_slot(
            db,
            space,
            SpaceSlotCreate(
                weekday=0, start_time=time(7, 0), end_time=time(8, 0), capacity=1
            ),
        )


def test_create_slot_rejects_overlap(db):
    _org(db)
    space = _space(db)
    service.create_slot(
        db,
        space,
        SpaceSlotCreate(weekday=2, start_time=time(10, 0), end_time=time(11, 0)),
    )
    db.flush()
    with pytest.raises(service.SlotOverlap):
        service.create_slot(
            db,
            space,
            SpaceSlotCreate(
                weekday=2, start_time=time(10, 30), end_time=time(11, 30)
            ),
        )


# --- Booking + capacity + waitlist ---------------------------------------


def test_first_booking_is_confirmed(db):
    _org(db)
    space = _space(db)
    target = _future(3)
    slot = _slot(db, space, target.weekday(), capacity=1)
    member = _member(db, 1)
    notifier = RecordingNotifier()

    booking = service.create_booking(db, member, slot.id, target, notifier=notifier)

    assert booking.status == "booked"
    assert notifier.calls[0][0] == "confirmation"


def test_full_slot_waitlists_next_booking(db):
    _org(db)
    space = _space(db)
    target = _future(3)
    slot = _slot(db, space, target.weekday(), capacity=1)
    m1, m2 = _member(db, 1), _member(db, 2)
    notifier = RecordingNotifier()

    service.create_booking(db, m1, slot.id, target, notifier=notifier)
    b2 = service.create_booking(db, m2, slot.id, target, notifier=notifier)

    assert b2.status == "waitlisted"
    assert notifier.calls[-1][0] == "waitlisted"
    assert notifier.calls[-1][1].position == 1


def test_full_slot_with_waitlist_disabled_raises(db):
    _org(db, booking_waitlist_enabled=False)
    space = _space(db)
    target = _future(3)
    slot = _slot(db, space, target.weekday(), capacity=1)
    m1, m2 = _member(db, 1), _member(db, 2)

    service.create_booking(db, m1, slot.id, target)
    with pytest.raises(service.SlotFull):
        service.create_booking(db, m2, slot.id, target)


def test_capacity_two_seats_two_before_waitlisting(db):
    _org(db)
    space = _space(db)
    target = _future(3)
    slot = _slot(db, space, target.weekday(), capacity=2)
    m1, m2, m3 = _member(db, 1), _member(db, 2), _member(db, 3)

    assert service.create_booking(db, m1, slot.id, target).status == "booked"
    assert service.create_booking(db, m2, slot.id, target).status == "booked"
    assert service.create_booking(db, m3, slot.id, target).status == "waitlisted"


def test_duplicate_booking_rejected(db):
    _org(db)
    space = _space(db)
    target = _future(3)
    slot = _slot(db, space, target.weekday(), capacity=5)
    m1 = _member(db, 1)

    service.create_booking(db, m1, slot.id, target)
    with pytest.raises(service.DuplicateBooking):
        service.create_booking(db, m1, slot.id, target)


def test_booking_in_past_rejected(db):
    _org(db)
    space = _space(db)
    past = date.today() - timedelta(days=3)
    slot = _slot(db, space, past.weekday(), capacity=1)
    m1 = _member(db, 1)

    with pytest.raises(service.BookingInPast):
        service.create_booking(db, m1, slot.id, past)


def test_booking_beyond_window_rejected(db):
    _org(db)
    space = _space(db)
    far = date.today() + timedelta(days=30)
    slot = _slot(db, space, far.weekday(), capacity=1)
    m1 = _member(db, 1)

    with pytest.raises(service.BookingWindowExceeded):
        service.create_booking(db, m1, slot.id, far)


def test_weekday_mismatch_rejected(db):
    _org(db)
    space = _space(db)
    target = _future(3)
    slot = _slot(db, space, target.weekday(), capacity=1)
    m1 = _member(db, 1)
    wrong_date = target + timedelta(days=1)

    with pytest.raises(service.WeekdayMismatch):
        service.create_booking(db, m1, slot.id, wrong_date)


# --- Cancellation + promotion --------------------------------------------


def test_cancel_promotes_earliest_waitlisted(db):
    _org(db, booking_cancellation_deadline_hours=0)
    space = _space(db)
    target = _future(3)
    slot = _slot(db, space, target.weekday(), capacity=1)
    m1, m2 = _member(db, 1), _member(db, 2)
    notifier = RecordingNotifier()

    b1 = service.create_booking(db, m1, slot.id, target, notifier=notifier)
    b2 = service.create_booking(db, m2, slot.id, target, notifier=notifier)
    assert b2.status == "waitlisted"

    canceller = _user(db, 9)
    service.cancel_booking(
        db, b1, cancelled_by_user_id=canceller.id, is_admin=False, notifier=notifier
    )
    db.refresh(b2)

    assert b1.status == "cancelled"
    assert b2.status == "booked"
    assert notifier.calls[-1][0] == "promoted"


def test_owner_cancel_past_deadline_rejected(db):
    _org(db, booking_cancellation_deadline_hours=1_000_000)
    space = _space(db)
    target = _future(3)
    slot = _slot(db, space, target.weekday(), capacity=1)
    m1 = _member(db, 1)

    b1 = service.create_booking(db, m1, slot.id, target)
    with pytest.raises(service.CancellationTooLate):
        service.cancel_booking(db, b1, cancelled_by_user_id=1, is_admin=False)


def test_admin_cancel_ignores_deadline(db):
    _org(db, booking_cancellation_deadline_hours=1_000_000)
    space = _space(db)
    target = _future(3)
    slot = _slot(db, space, target.weekday(), capacity=1)
    m1 = _member(db, 1)

    admin = _user(db, 8)
    b1 = service.create_booking(db, m1, slot.id, target)
    service.cancel_booking(db, b1, cancelled_by_user_id=admin.id, is_admin=True)
    assert b1.status == "cancelled"


# --- Availability ---------------------------------------------------------


def test_availability_reports_counts_and_state(db):
    _org(db)
    space = _space(db)
    target = _future(3)
    week_start = target - timedelta(days=target.weekday())  # Monday of that week
    slot = _slot(db, space, target.weekday(), capacity=1)
    m1 = _member(db, 1)
    service.create_booking(db, m1, slot.id, target)

    cells = service.space_week_availability(db, space, week_start, m1.id)
    cell = next(c for c in cells if c["space_slot_id"] == slot.id)

    assert cell["date"] == target
    assert cell["booked_count"] == 1
    assert cell["capacity"] == 1
    assert cell["my_status"] == "booked"
    assert cell["cell_state"] == "full"
