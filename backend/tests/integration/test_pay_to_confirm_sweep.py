"""Unpaid pending seats are released at their deadline, after a warning (#591)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.core.celery_app import celery
from app.domains.activities.registration_service import (
    admin_change_status,
    register_member,
    remind_pending_deadlines,
)
from app.domains.billing.seats import expire_unpaid_seats
from tests.integration.test_pay_to_confirm_registration import (
    _assert_counters_match_rows,
    _auto_cancel,
)
from tests.integration.test_registration_billing import (
    _activity,
    _member,
    _receipts_for,
    membership_type,  # noqa: F401 — fixture
    org,  # noqa: F401 — fixture
)

PAY = "pay_to_confirm"
NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
REMINDER = "app.tasks.email_tasks.send_deadline_reminder_email_task.delay"
UNPAID = "app.tasks.email_tasks.send_unpaid_cancellation_email_task.delay"


def _pending(db, org, membership_type, suffix, *, due_in, window=timedelta(hours=72), **kw):
    _auto_cancel(org, hours=72)
    activity, price = _activity(db, payment_flow=PAY, **kw)
    registration = register_member(
        db, activity, _member(db, membership_type, suffix), price.id
    )
    registration.payment_due_at = NOW + due_in
    registration.created_at = registration.payment_due_at - window
    db.flush()
    return activity, price, registration


class TestTheSweep:
    def test_releases_a_seat_past_its_deadline(self, db, org, membership_type):
        activity, _, registration = _pending(
            db, org, membership_type, "past", due_in=-timedelta(seconds=1)
        )

        assert expire_unpaid_seats(db, NOW) == 1

        assert registration.status == "cancelled"
        assert registration.cancelled_cause == "payment_expired"
        assert [r.status for r in _receipts_for(db, registration)] == ["cancelled"]
        _assert_counters_match_rows(db, activity)

    def test_leaves_a_seat_still_within_it(self, db, org, membership_type):
        _, _, registration = _pending(db, org, membership_type, "edge", due_in=timedelta(0))

        assert expire_unpaid_seats(db, NOW) == 0
        assert registration.status == "pending"

    def test_never_touches_a_seat_without_a_deadline(self, db, org, membership_type):
        activity, price = _activity(db, payment_flow=PAY)
        registration = register_member(
            db, activity, _member(db, membership_type, "no-deadline"), price.id
        )

        expire_unpaid_seats(db, NOW + timedelta(days=365))

        assert registration.status == "pending"

    def test_gives_the_seat_to_the_next_in_line(self, db, org, membership_type):
        activity, price, registration = _pending(
            db, org, membership_type, "casc", due_in=-timedelta(hours=1),
            max_participants=1,
        )
        waiting = register_member(
            db, activity, _member(db, membership_type, "casc-w"), price.id
        )

        expire_unpaid_seats(db, NOW)

        assert waiting.status == "pending"
        _assert_counters_match_rows(db, activity)

    def test_tells_the_member_after_the_commit(self, db, org, membership_type):
        _pending(db, org, membership_type, "mail", due_in=-timedelta(hours=1))

        with patch(UNPAID) as delay:
            expire_unpaid_seats(db, NOW)
            delay.assert_not_called()
            db.commit()

        delay.assert_called_once()

    def test_a_legacy_activity_has_nothing_to_sweep(self, db, org, membership_type):
        _auto_cancel(org)
        activity, price = _activity(db)
        registration = register_member(
            db, activity, _member(db, membership_type, "legacy"), price.id
        )

        expire_unpaid_seats(db, NOW + timedelta(days=365))

        assert registration.status == "confirmed"


class TestTheDeadlineReminder:
    def test_is_sent_once_within_a_day_of_the_deadline(self, db, org, membership_type):
        _, _, registration = _pending(
            db, org, membership_type, "remind", due_in=timedelta(hours=10)
        )

        with patch(REMINDER) as delay:
            assert remind_pending_deadlines(db, NOW) == 1
            assert remind_pending_deadlines(db, NOW + timedelta(hours=1)) == 0
            db.commit()

        delay.assert_called_once()
        assert registration.payment_reminder_sent_at == NOW

    def test_is_not_sent_too_early(self, db, org, membership_type):
        _pending(db, org, membership_type, "early", due_in=timedelta(hours=30))

        assert remind_pending_deadlines(db, NOW) == 0

    def test_a_short_window_is_warned_halfway(self, db, org, membership_type):
        _pending(
            db, org, membership_type, "short",
            due_in=timedelta(hours=3), window=timedelta(hours=4),
        )

        assert remind_pending_deadlines(db, NOW) == 0
        assert remind_pending_deadlines(db, NOW + timedelta(hours=1, minutes=1)) == 1

    def test_a_seat_put_back_to_pending_is_warned_again(self, db, org, membership_type):
        _, _, registration = _pending(
            db, org, membership_type, "again", due_in=timedelta(hours=10)
        )
        remind_pending_deadlines(db, NOW)

        admin_change_status(db, registration, "cancelled")
        admin_change_status(db, registration, "pending")

        assert registration.payment_reminder_sent_at is None


class TestTheSchedule:
    def test_runs_every_hour(self):
        entries = {e["task"]: e for e in celery.conf.beat_schedule.values()}
        schedule = entries["app.tasks.billing_tasks.scheduled_seat_deadlines"]["schedule"]
        assert schedule.hour == set(range(24))
