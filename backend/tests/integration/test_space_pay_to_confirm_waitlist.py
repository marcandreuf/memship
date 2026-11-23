"""What a freed seat in a paid slot does with the waiting list (#603).

It depends on the hold a booking taken now would get: at least the promotion
threshold (120 min) promotes the next waitlister to pending; between the
shortest hold (15 min) and the threshold, every waitlister is told and the
first to book takes it; under the shortest hold the seat is given up.
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.domains.billing.seats import BOOKING_SEAT_TEMPLATES
from app.domains.bookings import service
from app.domains.bookings.notifications import EmailBookingNotifier
from app.tasks.email_tasks import send_booking_email_task
from tests.integration.test_bookings_service import _member, _membership_type, _org
from tests.integration.test_space_pay_to_confirm_booking import (
    Recorder,
    _cutoff_leaving,
    _receipts,
    _slot,
    _space,
)


def _full_slot(db, waiting=1, **space_kwargs):
    """A one-seat slot held by a pending booking, with ``waiting`` behind it."""
    slot = _slot(db, _space(db, **space_kwargs), capacity=1)
    holder = service.create_booking(db, _member(db, 0), slot.id)
    waitlisters = [
        service.create_booking(db, _member(db, i + 1), slot.id) for i in range(waiting)
    ]
    assert all(w.status == "waitlisted" for w in waitlisters)
    return slot, holder, waitlisters


def _leave(db, slot, **bound):
    _org(db, booking_payment_cutoff_minutes=_cutoff_leaving(db, slot, **bound))


def _free_the_seat(db, holder):
    notifier = Recorder()
    service.cancel_booking(
        db, holder, cancelled_by_user_id=None, is_admin=True, notifier=notifier
    )
    return [(kind, note) for kind, note in notifier.calls if kind != "send_admin_cancellation"]


class TestAtLeastThePromotionThreshold:
    def test_the_next_waitlister_is_held_pending_and_told_how_to_pay(self, db):
        _org(db)
        slot, holder, [first, second] = _full_slot(db, waiting=2)
        _leave(db, slot, at_least=timedelta(minutes=120, seconds=5))

        calls = _free_the_seat(db, holder)

        assert first.status == "pending"
        assert first.payment_due_at is not None
        assert first.pending_since is not None
        assert first.waitlisted_at is None
        assert second.status == "waitlisted"
        [receipt] = _receipts(db, first)
        assert receipt.is_batchable is False
        [(kind, note)] = calls
        assert kind == "send_pending_payment"
        assert note.payment["promoted"] is True
        assert note.payment["amount"] == "12.10"


class TestBetweenTheShortestHoldAndTheThreshold:
    @pytest.mark.parametrize(
        "bound",
        [
            {"at_most": timedelta(minutes=119, seconds=30)},
            {"at_least": timedelta(minutes=15, seconds=5)},
        ],
        ids=["just-under-120", "just-over-15"],
    )
    def test_nobody_is_promoted_and_every_waitlister_is_told(self, db, bound):
        _org(db)
        slot, holder, waitlisters = _full_slot(db, waiting=2)
        _leave(db, slot, **bound)

        calls = _free_the_seat(db, holder)

        assert [w.status for w in waitlisters] == ["waitlisted", "waitlisted"]
        assert [kind for kind, _ in calls] == ["send_seat_available"] * 2
        assert {note.to for _, note in calls} == {
            w.member.person.email for w in waitlisters
        }
        offer = calls[0][1].payment
        assert offer["amount"] == "12.10"
        assert f"space={slot.space_id}" in offer["book_url"]

    def test_a_waitlister_who_books_takes_it_with_their_own_row(self, db):
        _org(db)
        slot, holder, [first, second] = _full_slot(db, waiting=2)
        _leave(db, slot, at_most=timedelta(minutes=60))
        _free_the_seat(db, holder)

        booked = service.create_booking(db, second.member, slot.id)

        assert booked.id == second.id
        assert booked.status == "pending"
        assert booked.waitlisted_at is None
        assert first.status == "waitlisted"

    def test_a_waitlister_cannot_book_while_the_slot_is_still_full(self, db):
        _org(db)
        slot, _, [first] = _full_slot(db)

        with pytest.raises(service.DuplicateBooking):
            service.create_booking(db, first.member, slot.id)

    def test_a_waitlister_no_longer_eligible_is_not_told(self, db):
        _org(db)
        allowed = _membership_type(db, "allowed-offer")
        other = _membership_type(db, "other-offer")
        slot = _slot(db, _space(db, allowed_membership_types=[allowed.id]), capacity=1)
        holder = service.create_booking(db, _member(db, 0, allowed), slot.id)
        stays = service.create_booking(db, _member(db, 1, allowed), slot.id)
        lapsed = service.create_booking(db, _member(db, 2, allowed), slot.id)
        lapsed.member.membership_type_id = other.id
        db.flush()
        _leave(db, slot, at_most=timedelta(minutes=60))

        calls = _free_the_seat(db, holder)

        assert [note.to for _, note in calls] == [stays.member.person.email]


class TestUnderTheShortestHold:
    def test_the_seat_is_given_up_in_silence(self, db):
        _org(db)
        slot, holder, [first] = _full_slot(db)
        _leave(db, slot, at_most=timedelta(minutes=14, seconds=30))

        calls = _free_the_seat(db, holder)

        assert first.status == "waitlisted"
        assert calls == []


class TestASeatWithNothingToPayUpfront:
    def test_a_free_slot_promotes_however_close_it_is(self, db):
        _org(db)
        space = _space(db)
        slot = _slot(db, space, capacity=1, price=Decimal("0"))
        holder = service.create_booking(db, _member(db, 0), slot.id)
        first = service.create_booking(db, _member(db, 1), slot.id)
        _leave(db, slot, at_most=timedelta(minutes=5))

        _free_the_seat(db, holder)

        assert first.status == "booked"

    def test_a_legacy_space_promotes_and_bills_as_before(self, db):
        _org(db)
        slot, holder, [first] = _full_slot(db, flow="legacy")
        _leave(db, slot, at_most=timedelta(minutes=5))

        calls = _free_the_seat(db, holder)

        assert first.status == "booked"
        [receipt] = _receipts(db, first)
        assert receipt.is_batchable is True
        [(kind, note)] = calls
        assert kind == "send_promoted"
        assert note.payment is None


class TestThePromotedMemberIsAlwaysTold:
    """The mail that tells a promotee they must pay is one a paid space cannot
    run without: seeded on, and refused to be switched off while a paid space
    exists. booking_promoted is neither, and was what this used to send, so
    with the default configuration a promotee was told nothing and released
    at the deadline. Held end to end: the notifier, the task, the template."""

    def test_through_a_template_a_paid_space_keeps_on(self, db):
        _org(db)
        slot, holder, [first] = _full_slot(db)
        _leave(db, slot, at_least=timedelta(minutes=120, seconds=5))
        queued = []

        with patch(
            "app.tasks.email_tasks.send_booking_email_task.delay",
            side_effect=lambda **kw: queued.append(kw),
        ):
            service.cancel_booking(
                db,
                holder,
                cancelled_by_user_id=None,
                is_admin=True,
                notifier=EmailBookingNotifier(),
            )
        [promotion] = [kw for kw in queued if kw["to"] == first.member.person.email]

        with patch("app.core.email._send_templated", return_value=True) as send:
            send_booking_email_task.run(**promotion)

        template = send.call_args.args[0]
        assert template in BOOKING_SEAT_TEMPLATES
        assert send.call_args.args[3]["promoted"] is True
