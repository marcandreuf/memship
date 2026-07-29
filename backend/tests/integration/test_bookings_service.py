"""Unit tests for the bookings service — slots, repeat series, capacity,
waitlist, promotion, windows.

Uses the transactional ``db`` fixture; the service never commits, so these flush
and query back within the same transaction.
"""

from datetime import date, time, timedelta

import pytest
from pydantic import ValidationError

from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.bookings import service
from app.domains.bookings.models import Space, SpaceSlot
from app.domains.bookings.schemas import (
    SlotRepeat,
    SpaceCreate,
    SpaceSlotCreate,
    SpaceSlotUpdate,
    SpaceUpdate,
)
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

    def send_admin_cancellation(self, note):
        self.calls.append(("admin_cancellation", note))


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


def _slot(db, space, on, capacity=1, start=time(10, 0), end=time(11, 0), series_id=None):
    slot = SpaceSlot(
        space_id=space.id,
        slot_date=on,
        start_time=start,
        end_time=end,
        capacity=capacity,
        series_id=series_id,
        is_active=True,
    )
    db.add(slot)
    db.flush()
    return slot


def _future(days=3):
    return date.today() + timedelta(days=days)


# --- Space opening hours --------------------------------------------------
#
# Two layers guard `close_time > open_time`: the create schema validates it, and
# the service re-checks on update. The update path needs the service check
# because SpaceUpdate is partial — a lone open_time can cross a close_time it
# never sees. The DB CHECK constraint is the last line, and reaching it means a
# 500 instead of a 422.


def test_create_space_rejects_close_before_open():
    with pytest.raises(ValidationError):
        SpaceCreate(name="Court", open_time=time(22, 0), close_time=time(8, 0))


def test_create_space_rejects_equal_hours():
    """A zero-length day is not a valid space — the bound is `<=`, not `<`."""
    with pytest.raises(ValidationError):
        SpaceCreate(name="Court", open_time=time(9, 0), close_time=time(9, 0))


def test_update_space_rejects_close_before_open(db):
    _org(db)
    space = _space(db)
    with pytest.raises(service.SlotOutsideOpeningHours):
        service.update_space(
            db, space, SpaceUpdate(open_time=time(22, 0), close_time=time(8, 0))
        )


def test_update_space_rejects_partial_open_time_crossing_close(db):
    """Only open_time is supplied, and it lands after the stored close_time.

    SpaceUpdate cannot catch this on its own — it never sees close_time — so the
    service comparing the merged values is what stops it.
    """
    _org(db)
    space = _space(db)  # 08:00–22:00
    with pytest.raises(service.SlotOutsideOpeningHours):
        service.update_space(db, space, SpaceUpdate(open_time=time(23, 0)))


def test_update_space_rejects_partial_close_time_crossing_open(db):
    _org(db)
    space = _space(db)  # 08:00–22:00
    with pytest.raises(service.SlotOutsideOpeningHours):
        service.update_space(db, space, SpaceUpdate(close_time=time(7, 0)))


def test_update_space_accepts_widened_hours(db):
    """The guard must not fire on a legitimate edit."""
    _org(db)
    space = _space(db)
    service.update_space(
        db, space, SpaceUpdate(open_time=time(7, 0), close_time=time(23, 0))
    )
    db.flush()

    assert space.open_time == time(7, 0)
    assert space.close_time == time(23, 0)


# --- Slot validation + creation -------------------------------------------


def test_create_slot_rejects_outside_opening_hours(db):
    _org(db)
    space = _space(db)
    with pytest.raises(service.SlotOutsideOpeningHours):
        service.create_slot(
            db,
            space,
            SpaceSlotCreate(
                slot_date=_future(3), start_time=time(7, 0), end_time=time(8, 0)
            ),
        )


def test_create_slot_rejects_overlap_on_same_date(db):
    _org(db)
    space = _space(db)
    on = _future(3)
    service.create_slot(
        db,
        space,
        SpaceSlotCreate(slot_date=on, start_time=time(10, 0), end_time=time(11, 0)),
    )
    db.flush()
    with pytest.raises(service.SlotOverlap):
        service.create_slot(
            db,
            space,
            SpaceSlotCreate(
                slot_date=on, start_time=time(10, 30), end_time=time(11, 30)
            ),
        )


def test_create_slot_in_past_rejected(db):
    _org(db)
    space = _space(db)
    with pytest.raises(service.SlotInPast):
        service.create_slot(
            db,
            space,
            SpaceSlotCreate(
                slot_date=date.today() - timedelta(days=1),
                start_time=time(10, 0),
                end_time=time(11, 0),
            ),
        )


def test_create_slot_all_day_uses_opening_hours(db):
    _org(db)
    space = _space(db)
    slots = service.create_slot(
        db, space, SpaceSlotCreate(slot_date=_future(3), all_day=True)
    )
    assert len(slots) == 1
    assert slots[0].start_time == space.open_time
    assert slots[0].end_time == space.close_time


def test_create_slot_repeat_generates_dated_series(db):
    _org(db)
    space = _space(db)
    start = _future(7)  # a full week out so every weekday lands in the future
    slots = service.create_slot(
        db,
        space,
        SpaceSlotCreate(
            slot_date=start,
            start_time=time(10, 0),
            end_time=time(11, 0),
            repeat=SlotRepeat(
                weekdays=[start.weekday()], interval_weeks=1, count=3
            ),
        ),
    )
    assert [s.slot_date for s in slots] == [
        start, start + timedelta(weeks=1), start + timedelta(weeks=2)
    ]
    assert len({s.series_id for s in slots}) == 1
    assert slots[0].series_id is not None


def test_create_slot_repeat_multiple_weekdays_skips_before_start(db):
    _org(db)
    space = _space(db)
    start = _future(14)
    weekdays = sorted({start.weekday(), (start.weekday() + 2) % 7, (start.weekday() + 6) % 7})
    slots = service.create_slot(
        db,
        space,
        SpaceSlotCreate(
            slot_date=start,
            start_time=time(10, 0),
            end_time=time(11, 0),
            repeat=SlotRepeat(weekdays=weekdays, interval_weeks=1, count=2),
        ),
    )
    # Week zero contributes only selected weekdays falling on/after the picked
    # date; week one contributes all of them.
    week0_expected = sum(1 for wd in weekdays if wd >= start.weekday())
    assert all(s.slot_date >= start for s in slots)
    assert len(slots) == week0_expected + len(weekdays)
    week1_monday = start + timedelta(days=7 - start.weekday())
    weekdays_week1 = sorted(
        s.slot_date.weekday() for s in slots if s.slot_date >= week1_monday
    )
    assert weekdays_week1 == weekdays


def test_create_slot_repeat_conflict_rejects_whole_batch(db):
    _org(db)
    space = _space(db)
    start = _future(7)
    # An existing slot on the second occurrence's date.
    _slot(db, space, start + timedelta(weeks=1))
    before = db.query(SpaceSlot).count()
    with pytest.raises(service.SlotOverlap) as exc:
        service.create_slot(
            db,
            space,
            SpaceSlotCreate(
                slot_date=start,
                start_time=time(10, 0),
                end_time=time(11, 0),
                repeat=SlotRepeat(
                    weekdays=[start.weekday()], interval_weeks=1, count=3
                ),
            ),
        )
    assert (start + timedelta(weeks=1)).isoformat() in str(exc.value)
    assert db.query(SpaceSlot).count() == before  # nothing created


# --- Series edits ----------------------------------------------------------


def _series(db, space, count=3):
    start = _future(7)
    return service.create_slot(
        db,
        space,
        SpaceSlotCreate(
            slot_date=start,
            start_time=time(10, 0),
            end_time=time(11, 0),
            repeat=SlotRepeat(weekdays=[start.weekday()], interval_weeks=1, count=count),
        ),
    )


def test_update_slot_one_touches_only_target(db):
    _org(db)
    space = _space(db)
    slots = _series(db, space)
    db.flush()
    service.update_slot(
        db, space, slots[1], SpaceSlotUpdate(capacity=5), apply_to="one"
    )
    assert slots[0].capacity == 1
    assert slots[1].capacity == 5
    assert slots[2].capacity == 1


def test_update_slot_upcoming_applies_from_target_on(db):
    _org(db)
    space = _space(db)
    slots = _series(db, space)
    db.flush()
    service.update_slot(
        db,
        space,
        slots[1],
        SpaceSlotUpdate(start_time=time(12, 0), end_time=time(13, 0), capacity=4),
        apply_to="upcoming",
    )
    assert slots[0].start_time == time(10, 0) and slots[0].capacity == 1
    for s in slots[1:]:
        assert s.start_time == time(12, 0)
        assert s.capacity == 4


def test_series_sizes_upcoming(db):
    _org(db)
    space = _space(db)
    slots = _series(db, space, count=3)
    one_off = _slot(db, space, _future(4), start=time(15, 0), end=time(16, 0))
    db.flush()
    sizes = service.series_sizes_upcoming(service.list_slots(db, space.id))
    assert sizes[slots[0].id] == 3
    assert sizes[slots[1].id] == 2
    assert sizes[slots[2].id] == 1
    assert sizes[one_off.id] == 1


# --- Booking + capacity + waitlist ---------------------------------------


def test_first_booking_is_confirmed(db):
    _org(db)
    space = _space(db)
    slot = _slot(db, space, _future(3), capacity=1)
    member = _member(db, 1)
    notifier = RecordingNotifier()

    booking = service.create_booking(db, member, slot.id, notifier=notifier)

    assert booking.status == "booked"
    assert notifier.calls[0][0] == "confirmation"


def test_full_slot_waitlists_next_booking(db):
    _org(db)
    space = _space(db)
    slot = _slot(db, space, _future(3), capacity=1)
    m1, m2 = _member(db, 1), _member(db, 2)
    notifier = RecordingNotifier()

    service.create_booking(db, m1, slot.id, notifier=notifier)
    b2 = service.create_booking(db, m2, slot.id, notifier=notifier)

    assert b2.status == "waitlisted"
    assert notifier.calls[-1][0] == "waitlisted"
    assert notifier.calls[-1][1].position == 1


def test_full_slot_with_waitlist_disabled_raises(db):
    _org(db, booking_waitlist_enabled=False)
    space = _space(db)
    slot = _slot(db, space, _future(3), capacity=1)
    m1, m2 = _member(db, 1), _member(db, 2)

    service.create_booking(db, m1, slot.id)
    with pytest.raises(service.SlotFull):
        service.create_booking(db, m2, slot.id)


def test_capacity_two_seats_two_before_waitlisting(db):
    _org(db)
    space = _space(db)
    slot = _slot(db, space, _future(3), capacity=2)
    m1, m2, m3 = _member(db, 1), _member(db, 2), _member(db, 3)

    assert service.create_booking(db, m1, slot.id).status == "booked"
    assert service.create_booking(db, m2, slot.id).status == "booked"
    assert service.create_booking(db, m3, slot.id).status == "waitlisted"


def test_duplicate_booking_rejected(db):
    _org(db)
    space = _space(db)
    slot = _slot(db, space, _future(3), capacity=5)
    m1 = _member(db, 1)

    service.create_booking(db, m1, slot.id)
    with pytest.raises(service.DuplicateBooking):
        service.create_booking(db, m1, slot.id)


def test_booking_past_slot_rejected(db):
    _org(db)
    space = _space(db)
    slot = _slot(db, space, date.today() - timedelta(days=3), capacity=1)
    m1 = _member(db, 1)

    with pytest.raises(service.BookingInPast):
        service.create_booking(db, m1, slot.id)


def test_booking_a_deactivated_slot_rejected(db):
    """A deactivated slot is invisible, not merely unbookable.

    The service reports SlotNotFound rather than a distinct "inactive" error so
    a caller cannot probe which slot ids exist behind a withdrawn slot.
    """
    _org(db)
    space = _space(db)
    slot = _slot(db, space, _future(3), capacity=5)
    slot.is_active = False
    db.flush()
    m1 = _member(db, 1)

    with pytest.raises(service.SlotNotFound):
        service.create_booking(db, m1, slot.id)


def test_booking_an_active_slot_in_a_deactivated_space_rejected(db):
    """Deactivating a space must close its slots without touching each one."""
    _org(db)
    space = _space(db)
    slot = _slot(db, space, _future(3), capacity=5)
    service.deactivate_space(db, space)
    db.flush()
    m1 = _member(db, 1)

    assert slot.is_active is True
    with pytest.raises(service.SlotNotFound):
        service.create_booking(db, m1, slot.id)


def test_deactivated_slot_absent_from_week_availability(db):
    """The calendar and the booking guard must agree on what is bookable."""
    _org(db)
    space = _space(db)
    target = _future(3)
    week_start = target - timedelta(days=target.weekday())
    live = _slot(db, space, target, capacity=1, start=time(10, 0), end=time(11, 0))
    hidden = _slot(db, space, target, capacity=1, start=time(12, 0), end=time(13, 0))
    hidden.is_active = False
    db.flush()
    m1 = _member(db, 1)

    ids = {
        c["space_slot_id"]
        for c in service.space_week_availability(db, space, week_start, m1.id)
    }

    assert live.id in ids
    assert hidden.id not in ids


def test_reactivating_a_slot_makes_it_bookable_again(db):
    """Deactivation is reversible — it must not strand the slot permanently."""
    _org(db)
    space = _space(db)
    slot = _slot(db, space, _future(3), capacity=5)
    slot.is_active = False
    db.flush()
    m1 = _member(db, 1)

    with pytest.raises(service.SlotNotFound):
        service.create_booking(db, m1, slot.id)

    slot.is_active = True
    db.flush()

    assert service.create_booking(db, m1, slot.id).status == "booked"


def test_booking_beyond_window_rejected(db):
    _org(db)
    space = _space(db)
    slot = _slot(db, space, date.today() + timedelta(days=30), capacity=1)
    m1 = _member(db, 1)

    with pytest.raises(service.BookingWindowExceeded):
        service.create_booking(db, m1, slot.id)


# --- Cancellation + promotion --------------------------------------------


def test_cancel_promotes_earliest_waitlisted(db):
    _org(db, booking_cancellation_deadline_hours=0)
    space = _space(db)
    slot = _slot(db, space, _future(3), capacity=1)
    m1, m2 = _member(db, 1), _member(db, 2)
    notifier = RecordingNotifier()

    b1 = service.create_booking(db, m1, slot.id, notifier=notifier)
    b2 = service.create_booking(db, m2, slot.id, notifier=notifier)
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
    slot = _slot(db, space, _future(3), capacity=1)
    m1 = _member(db, 1)

    b1 = service.create_booking(db, m1, slot.id)
    with pytest.raises(service.CancellationTooLate):
        service.cancel_booking(db, b1, cancelled_by_user_id=1, is_admin=False)


def test_admin_cancel_ignores_deadline(db):
    _org(db, booking_cancellation_deadline_hours=1_000_000)
    space = _space(db)
    slot = _slot(db, space, _future(3), capacity=1)
    m1 = _member(db, 1)

    admin = _user(db, 8)
    b1 = service.create_booking(db, m1, slot.id)
    service.cancel_booking(db, b1, cancelled_by_user_id=admin.id, is_admin=True)
    assert b1.status == "cancelled"


def test_admin_cancel_notifies_member(db):
    _org(db)
    space = _space(db)
    slot = _slot(db, space, _future(3), capacity=1)
    m1 = _member(db, 1)
    notifier = RecordingNotifier()

    admin = _user(db, 8)
    b1 = service.create_booking(db, m1, slot.id, notifier=notifier)
    service.cancel_booking(
        db, b1, cancelled_by_user_id=admin.id, is_admin=True, notifier=notifier
    )

    kinds = [k for k, _ in notifier.calls]
    assert kinds[-1] == "admin_cancellation"
    assert notifier.calls[-1][1].to == "m1@t.com"


def test_member_self_cancel_sends_no_cancellation_email(db):
    _org(db, booking_cancellation_deadline_hours=0)
    space = _space(db)
    slot = _slot(db, space, _future(3), capacity=1)
    m1 = _member(db, 1)
    canceller = _user(db, 7)
    notifier = RecordingNotifier()

    b1 = service.create_booking(db, m1, slot.id, notifier=notifier)
    service.cancel_booking(
        db, b1, cancelled_by_user_id=canceller.id, is_admin=False, notifier=notifier
    )

    assert "admin_cancellation" not in [k for k, _ in notifier.calls]


# --- Destructive deletes notify affected members ---------------------------


def test_forced_slot_delete_notifies_each_affected_member(db):
    _org(db)
    space = _space(db)
    slot = _slot(db, space, _future(3), capacity=1)
    m1, m2 = _member(db, 1), _member(db, 2)
    service.create_booking(db, m1, slot.id)
    service.create_booking(db, m2, slot.id)  # waitlisted — also loses a spot
    notifier = RecordingNotifier()

    with pytest.raises(service.HasActiveBookings):
        service.delete_slot(db, slot, notifier=notifier)
    assert notifier.calls == []  # refused → nobody emailed

    service.delete_slot(db, slot, force=True, notifier=notifier)
    kinds = [k for k, _ in notifier.calls]
    assert kinds == ["admin_cancellation", "admin_cancellation"]
    assert {n.to for _, n in notifier.calls} == {"m1@t.com", "m2@t.com"}


def test_forced_space_delete_notifies_affected_members(db):
    _org(db)
    space = _space(db)
    s1 = _slot(db, space, _future(3))
    s2 = _slot(db, space, _future(4), start=time(15, 0), end=time(16, 0))
    m1, m2 = _member(db, 1), _member(db, 2)
    service.create_booking(db, m1, s1.id)
    service.create_booking(db, m2, s2.id)
    notifier = RecordingNotifier()

    affected = service.delete_space(db, space, force=True, notifier=notifier)
    assert len(affected) == 2
    assert {n.to for _, n in notifier.calls} == {"m1@t.com", "m2@t.com"}


def test_past_bookings_do_not_block_delete(db):
    _org(db)
    space = _space(db)
    slot = _slot(db, space, date.today() - timedelta(days=7))
    m1 = _member(db, 1)
    from app.domains.bookings.models import Booking

    db.add(Booking(space_slot_id=slot.id, member_id=m1.id, status="booked"))
    db.flush()
    notifier = RecordingNotifier()

    # Only today-or-future bookings count as affected; history never blocks.
    service.delete_slot(db, slot, notifier=notifier)
    assert notifier.calls == []


def test_email_notifier_dispatch_failure_never_raises(db, monkeypatch):
    from app.domains.bookings.notifications import (
        BookingNotification,
        EmailBookingNotifier,
    )

    import app.tasks.email_tasks as tasks

    class Boom:
        def delay(self, **kwargs):
            raise RuntimeError("broker down")

    monkeypatch.setattr(tasks, "send_booking_email_task", Boom())
    note = BookingNotification(
        to="x@t.com", member_name="X", space_name="Court",
        date_str="24/07/2026", time_str="10:00–11:00",
    )
    EmailBookingNotifier().send_admin_cancellation(note)  # must not raise


# --- Availability + my bookings -------------------------------------------


def test_availability_reports_counts_and_state(db):
    _org(db)
    space = _space(db)
    target = _future(3)
    week_start = target - timedelta(days=target.weekday())  # Monday of that week
    slot = _slot(db, space, target, capacity=1)
    m1 = _member(db, 1)
    service.create_booking(db, m1, slot.id)

    cells = service.space_week_availability(db, space, week_start, m1.id)
    cell = next(c for c in cells if c["space_slot_id"] == slot.id)

    assert cell["date"] == target
    assert cell["weekday"] == target.weekday()
    assert cell["booked_count"] == 1
    assert cell["capacity"] == 1
    assert cell["my_status"] == "booked"
    assert cell["cell_state"] == "full"


def test_availability_only_covers_slots_dated_in_week(db):
    _org(db)
    space = _space(db)
    target = _future(3)
    week_start = target - timedelta(days=target.weekday())
    _slot(db, space, target)
    _slot(db, space, target + timedelta(days=14), start=time(12, 0), end=time(13, 0))

    cells = service.space_week_availability(db, space, week_start, None)
    assert [c["date"] for c in cells] == [target]


def test_my_bookings_reports_occupancy(db):
    _org(db)
    space = _space(db)
    slot = _slot(db, space, _future(3), capacity=3)
    m1, m2 = _member(db, 1), _member(db, 2)
    service.create_booking(db, m1, slot.id)
    service.create_booking(db, m2, slot.id)

    mine = service.my_bookings(db, m1.id, scope="upcoming")
    assert len(mine) == 1
    assert mine[0]["slot_date"] == slot.slot_date
    assert mine[0]["capacity"] == 3
    assert mine[0]["booked_count"] == 2
