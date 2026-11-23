"""The sweep that releases unpaid bookings, the warning before it, and what
switching auto-cancel on does to bookings already held (#603)."""

from datetime import datetime, timedelta, timezone

from app.core.celery_app import celery
from app.core.clock import org_timezone
from app.domains.billing.seats import expire_unpaid_seats
from app.domains.bookings import service
from tests.integration.test_bookings_service import _member, _org
from tests.integration.test_receipt_payment import _auth_cookie, _create_admin
from tests.integration.test_space_pay_to_confirm_booking import (
    Recorder,
    _receipts,
    _slot,
    _space,
)
from tests.integration.test_space_pay_to_confirm_payment import _pending

NOW = datetime.now(timezone.utc)


def _kinds(notifier):
    return [kind for kind, _ in notifier.calls]


class TestTheSweep:
    def test_releases_a_booking_past_its_deadline(self, db):
        _org(db)
        _, booking, receipt = _pending(db)
        notifier = Recorder()

        [expired] = service.expired_pending_bookings(db, booking.payment_due_at + timedelta(seconds=1))
        service.expire_unpaid_booking(db, expired, notifier=notifier)

        assert booking.status == "cancelled"
        assert booking.cancelled_cause == "payment_expired"
        assert receipt.status == "cancelled"
        assert _kinds(notifier) == ["send_cancelled_unpaid"]

    def test_leaves_one_whose_deadline_is_now(self, db):
        _org(db)
        _, booking, _ = _pending(db)

        assert service.expired_pending_bookings(db, booking.payment_due_at) == []

    def test_is_part_of_the_seat_sweep(self, db):
        _org(db)
        _, booking, _ = _pending(db)

        assert expire_unpaid_seats(db, booking.payment_due_at + timedelta(seconds=1)) == 1
        assert booking.status == "cancelled"

    def test_leaves_a_paid_booking_alone(self, db):
        _org(db)
        slot = _slot(db, _space(db, flow="legacy"))
        booking = service.create_booking(db, _member(db), slot.id)

        assert expire_unpaid_seats(db, NOW + timedelta(days=365)) == 0
        assert booking.status == "booked"

    def test_offers_the_released_seat_on(self, db):
        _org(db, booking_auto_cancel_enabled=True, booking_auto_cancel_hours=3)
        slot, booking, _ = _pending(db)
        waiting = service.create_booking(db, _member(db, 5), slot.id)
        assert waiting.status == "waitlisted"

        # Released three hours in; the slot is still days away, so the next
        # hold is long enough to promote.
        [expired] = service.expired_pending_bookings(db, booking.payment_due_at + timedelta(seconds=1))
        service.expire_unpaid_booking(db, expired)

        assert waiting.status == "pending"
        assert _receipts(db, waiting)

    def test_runs_every_five_minutes(self):
        schedule = celery.conf.beat_schedule["scheduled-seat-deadlines"]["schedule"]
        assert schedule.minute == set(range(0, 60, 5))


class TestTheWarning:
    def _held(self, db, window):
        _org(db)
        _, booking, _ = _pending(db)
        booking.pending_since = booking.payment_due_at - window
        return booking

    def test_a_short_window_is_warned_halfway_through_it(self, db):
        booking = self._held(db, timedelta(hours=2))
        notifier = Recorder()
        due = booking.payment_due_at

        assert service.remind_booking_deadlines(db, due - timedelta(minutes=61), notifier=notifier) == 0
        assert service.remind_booking_deadlines(db, due - timedelta(minutes=59), notifier=notifier) == 1
        assert _kinds(notifier) == ["send_deadline_reminder"]
        assert notifier.calls[0][1].payment["amount"] == "12.10"

    def test_a_long_window_is_warned_a_day_ahead(self, db):
        booking = self._held(db, timedelta(days=5))
        due = booking.payment_due_at

        assert service.remind_booking_deadlines(db, due - timedelta(hours=25)) == 0
        assert service.remind_booking_deadlines(db, due - timedelta(hours=23)) == 1

    def test_only_once(self, db):
        booking = self._held(db, timedelta(hours=2))
        at = booking.payment_due_at - timedelta(minutes=30)

        service.remind_booking_deadlines(db, at)

        assert service.remind_booking_deadlines(db, at + timedelta(minutes=5)) == 0

    def test_the_window_runs_from_when_the_hold_began(self, db):
        # Auto-cancel is a day, but the cut-off left this hold three hours: it
        # is warned an hour and a half before, not twelve hours.
        _org(db, booking_auto_cancel_enabled=True, booking_auto_cancel_hours=24)
        _, booking, _ = _pending(db)
        booking.pending_since = booking.payment_due_at - timedelta(hours=3)
        due = booking.payment_due_at

        assert service.remind_booking_deadlines(db, due - timedelta(hours=2)) == 0
        assert service.remind_booking_deadlines(db, due - timedelta(hours=1)) == 1


class TestSwitchingAutoCancelOn:
    def test_on_the_space_brings_its_bookings_deadlines_forward(self, db):
        _org(db)
        slot, booking, receipt = _pending(db)
        space = slot.space
        before = booking.payment_due_at
        notifier = Recorder()

        space.auto_cancel_enabled = True
        space.auto_cancel_hours = 6
        assert service.shorten_pending_deadlines(db, [space], notifier=notifier) == 1

        assert booking.payment_due_at < before
        assert booking.payment_due_at <= datetime.now(timezone.utc) + timedelta(hours=6)
        # The club's date, not UTC's: six hours from early evening is already
        # tomorrow in Madrid while still today in UTC.
        assert receipt.due_date == booking.payment_due_at.astimezone(org_timezone(db)).date()
        [(kind, note)] = notifier.calls
        assert kind == "send_pending_payment"
        assert note.payment["deadline_changed"] is True

    def test_a_deadline_already_sooner_is_kept(self, db):
        _org(db)
        slot, booking, _ = _pending(db)
        sooner = datetime.now(timezone.utc) + timedelta(hours=2)
        booking.payment_due_at = sooner
        slot.space.auto_cancel_enabled = True
        slot.space.auto_cancel_hours = 6

        assert service.shorten_pending_deadlines(db, [slot.space]) == 0
        assert booking.payment_due_at == sooner

    def test_for_the_club_reaches_spaces_that_follow_it(self, client, db):
        _org(db)
        slot, following, _ = _pending(db)
        own_slot, keeps, _ = _pending(db, 1, auto_cancel_enabled=False)
        before = (following.payment_due_at, keeps.payment_due_at)
        admin = _create_admin(db, "booking-auto-cancel-club")

        resp = client.put(
            "/api/v1/settings/",
            json={"features": {"booking_auto_cancel_enabled": True, "booking_auto_cancel_hours": 6}},
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 200, resp.text
        db.expire_all()
        assert following.payment_due_at < before[0]
        assert keeps.payment_due_at == before[1]


class TestSwitchingAutoCancelOnThroughTheSpace:
    def test_the_space_update_brings_deadlines_forward(self, db):
        _org(db)
        slot, booking, _ = _pending(db)
        before = booking.payment_due_at

        service.update_space(
            db,
            slot.space,
            service.SpaceUpdate(auto_cancel_enabled=True, auto_cancel_hours=6),
        )

        assert booking.payment_due_at < before
