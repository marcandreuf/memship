"""Booking a paid slot in a pay-to-confirm space holds it as pending (#603).

Every pending booking has a deadline: the slot's start less the club's cut-off,
or earlier when auto-cancel is on. A booking that would get less than the
club's shortest hold is refused instead of created already doomed.
"""

import math
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.core.clock import org_timezone
from app.domains.billing.models import Receipt
from app.domains.billing.payment_instructions import receipt_allowed_methods
from app.domains.bookings import service
from app.domains.bookings.models import Booking, Space, SpaceSlot
from tests.integration.test_bookings_service import _member, _org

PRICE = Decimal("10.00")
BROKEN = "app.domains.billing.service.generate_booking_receipt"


class Recorder:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        if not name.startswith("send_"):
            raise AttributeError(name)
        return lambda note: self.calls.append((name, note))


def _space(db, *, price=PRICE, flow="pay_to_confirm", methods=("cash",), **extra):
    space = Space(
        name="Court 1",
        open_time=time(0, 0),
        close_time=time(23, 59),
        is_active=True,
        price=price,
        payment_flow=flow,
        payment_methods=list(methods),
        **extra,
    )
    db.add(space)
    db.flush()
    return space


def _slot(db, space, *, days=3, start=time(10, 0), capacity=1, price=None):
    slot = SpaceSlot(
        space_id=space.id,
        slot_date=datetime.now(org_timezone(db)).date() + timedelta(days=days),
        start_time=start,
        end_time=time(start.hour + 1, start.minute),
        capacity=capacity,
        price=price,
        is_active=True,
    )
    db.add(slot)
    db.flush()
    return slot


def _start(db, slot) -> datetime:
    return datetime.combine(slot.slot_date, slot.start_time, tzinfo=org_timezone(db))


def _receipts(db, booking):
    db.flush()
    return db.query(Receipt).filter(Receipt.booking_id == booking.id).all()


def _book(db, slot, i=0, notifier=None):
    return service.create_booking(db, _member(db, i), slot.id, notifier=notifier)


class TestAPaidBookingIsPending:
    def test_it_waits_for_payment_and_remembers_when_the_hold_began(self, db):
        _org(db)
        slot = _slot(db, _space(db))
        before = datetime.now(timezone.utc)

        booking = _book(db, slot)

        assert booking.status == "pending"
        assert before <= booking.pending_since <= datetime.now(timezone.utc)

    def test_its_receipt_is_due_on_the_deadline_and_never_batched(self, db):
        _org(db)
        slot = _slot(db, _space(db))

        booking = _book(db, slot)

        [receipt] = _receipts(db, booking)
        assert receipt.status == "emitted"
        assert receipt.is_batchable is False
        assert receipt.due_date == booking.payment_due_at.astimezone(
            org_timezone(db)
        ).date()

    def test_the_member_is_told_how_much_by_when_and_how(self, db):
        _org(db)
        slot = _slot(db, _space(db))
        notifier = Recorder()

        booking = _book(db, slot, notifier=notifier)

        [(kind, note)] = notifier.calls
        assert kind == "send_pending_payment"
        assert note.payment["amount"] == "12.10"
        assert note.payment["cash"] is True
        assert note.payment["deadline"] == booking.payment_due_at.astimezone(
            org_timezone(db)
        ).strftime("%d/%m/%Y %H:%M")

    def test_it_holds_its_seat(self, db):
        _org(db)
        slot = _slot(db, _space(db), capacity=1)

        _book(db, slot, 1)
        second = _book(db, slot, 2)

        assert second.status == "waitlisted"

    def test_a_pending_row_blocks_booking_the_slot_again(self, db):
        _org(db)
        slot = _slot(db, _space(db), capacity=2)
        member = _member(db, 3)
        service.create_booking(db, member, slot.id)

        with pytest.raises(service.DuplicateBooking):
            service.create_booking(db, member, slot.id)

    def test_its_receipt_only_takes_what_the_space_accepts(self, db):
        _org(db)
        slot = _slot(db, _space(db, methods=("cash", "transfer")))

        [receipt] = _receipts(db, _book(db, slot))

        assert receipt_allowed_methods(receipt) == ["cash", "transfer"]


class TestWhatIsNotPending:
    def test_a_free_slot_in_a_paid_space_is_booked_with_no_receipt(self, db):
        _org(db)
        slot = _slot(db, _space(db), price=Decimal("0"))

        booking = _book(db, slot)

        assert booking.status == "booked"
        assert booking.payment_due_at is None
        assert _receipts(db, booking) == []

    def test_a_legacy_space_books_and_bills_as_before(self, db):
        _org(db)
        slot = _slot(db, _space(db, flow="legacy"))

        booking = _book(db, slot)

        assert booking.status == "booked"
        assert booking.payment_due_at is None
        [receipt] = _receipts(db, booking)
        assert receipt.is_batchable is True
        assert receipt.due_date is None
        assert receipt_allowed_methods(receipt) is None


class TestTheDeadline:
    def test_without_auto_cancel_it_is_the_cut_off_before_the_slot(self, db):
        _org(db, booking_payment_cutoff_minutes=90)
        slot = _slot(db, _space(db))

        booking = _book(db, slot)

        assert booking.payment_due_at == _start(db, slot) - timedelta(minutes=90)

    def test_auto_cancel_brings_it_earlier(self, db):
        _org(db, booking_auto_cancel_enabled=True, booking_auto_cancel_hours=6)
        slot = _slot(db, _space(db), days=3)
        before = datetime.now(timezone.utc)

        due = _book(db, slot).payment_due_at

        assert before + timedelta(hours=6) <= due <= datetime.now(timezone.utc) + timedelta(hours=6)

    def test_the_cut_off_wins_when_it_comes_first(self, db):
        _org(db, booking_auto_cancel_enabled=True, booking_auto_cancel_hours=8760)
        slot = _slot(db, _space(db), days=3)

        booking = _book(db, slot)

        assert booking.payment_due_at == _start(db, slot) - timedelta(minutes=60)

    def test_the_space_overrides_the_club(self, db):
        _org(db, booking_auto_cancel_enabled=True, booking_auto_cancel_hours=6)
        slot = _slot(db, _space(db, auto_cancel_enabled=False), days=3)

        booking = _book(db, slot)

        assert booking.payment_due_at == _start(db, slot) - timedelta(minutes=60)


def _cutoff_leaving(db, slot, at_most: timedelta | None = None, at_least: timedelta | None = None) -> int:
    """A cut-off, in whole minutes, leaving at most or at least the given time
    to pay. Whole minutes are coarser than the clock, hence the two bounds."""
    until = (_start(db, slot) - datetime.now(timezone.utc)).total_seconds()
    if at_most is not None:
        return math.ceil((until - at_most.total_seconds()) / 60)
    return math.floor((until - at_least.total_seconds()) / 60)


class TestTheShortestHold:
    def test_a_booking_with_less_is_refused_and_told_why(self, db):
        _org(db)
        slot = _slot(db, _space(db))
        _org(db, booking_payment_cutoff_minutes=_cutoff_leaving(db, slot, at_most=timedelta(minutes=14, seconds=30)))

        with pytest.raises(service.BookingHoldTooShort) as exc:
            _book(db, slot)

        assert exc.value.fields["cutoff_minutes"] > 0
        assert datetime.fromisoformat(exc.value.fields["pay_by"]) < _start(db, slot)
        assert db.query(Booking).filter(Booking.space_slot_id == slot.id).count() == 0

    def test_a_booking_with_the_minimum_is_held(self, db):
        _org(db)
        slot = _slot(db, _space(db))
        _org(db, booking_payment_cutoff_minutes=_cutoff_leaving(db, slot, at_least=timedelta(minutes=15, seconds=5)))

        assert _book(db, slot).status == "pending"

    def test_a_full_slot_still_waitlists(self, db):
        _org(db)
        slot = _slot(db, _space(db), capacity=1)
        _book(db, slot, 1)
        _org(db, booking_payment_cutoff_minutes=_cutoff_leaving(db, slot, at_most=timedelta(minutes=5)))

        assert _book(db, slot, 2).status == "waitlisted"


class TestAReceiptThatCannotBeRaised:
    def test_fails_a_pending_booking(self, db):
        _org(db)
        slot = _slot(db, _space(db))

        with patch(BROKEN, side_effect=RuntimeError("no numbering series")):
            with pytest.raises(service.SeatReceiptFailed):
                _book(db, slot)

    def test_leaves_a_legacy_booking_standing(self, db):
        _org(db)
        slot = _slot(db, _space(db, flow="legacy"))

        with patch(BROKEN, side_effect=RuntimeError("no numbering series")):
            booking = _book(db, slot)

        assert booking.status == "booked"


class TestTheWeek:
    def _cell(self, db, space, slot):
        week = slot.slot_date - timedelta(days=slot.slot_date.weekday())
        [cell] = [
            c
            for c in service.space_week_availability(db, space, week, None)
            if c["space_slot_id"] == slot.id
        ]
        return cell

    def test_says_when_a_booking_now_would_have_to_be_paid(self, db):
        _org(db)
        space = _space(db)
        slot = _slot(db, space)

        cell = self._cell(db, space, slot)

        assert cell["cell_state"] == "open"
        assert cell["pay_by"] == _start(db, slot) - timedelta(minutes=60)

    def test_counts_a_pending_booking_as_taken(self, db):
        _org(db)
        space = _space(db)
        slot = _slot(db, space, capacity=1)
        _book(db, slot)

        cell = self._cell(db, space, slot)

        assert cell["booked_count"] == 1
        assert cell["cell_state"] == "full"

    def test_does_not_offer_a_slot_too_close_to_hold(self, db):
        _org(db)
        space = _space(db)
        slot = _slot(db, space)
        _org(db, booking_payment_cutoff_minutes=_cutoff_leaving(db, slot, at_most=timedelta(minutes=10)))

        assert self._cell(db, space, slot)["cell_state"] == "too_late"

    def test_a_legacy_space_has_nothing_to_pay_upfront(self, db):
        _org(db)
        space = _space(db, flow="legacy")
        slot = _slot(db, space)

        cell = self._cell(db, space, slot)

        assert cell["pay_by"] is None
        assert cell["cell_state"] == "open"
