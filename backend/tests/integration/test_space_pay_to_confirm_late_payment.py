"""A payment that arrives after its booking was released is recorded, not lost (#603).

The booking is given back if the slot has not started and a seat is free;
otherwise the money is owed back. The club is alerted either way, and a member
left without a seat is not told "payment received, nothing more to do".
"""

from datetime import date, timedelta
from unittest.mock import patch

from app.domains.billing.seats import expire_unpaid_seats, record_late_payment
from app.domains.bookings import service
from tests.integration.test_bookings_service import _member, _org
from tests.integration.test_pay_to_confirm_payment import (
    _post_stripe_paid,
    _stripe_provider,
)
from tests.integration.test_space_pay_to_confirm_payment import _pending, _reloaded

ALERT = "app.tasks.email_tasks.send_late_payment_alert_email_task.delay"


def _released(db, *, taken=False):
    """A booking released unpaid; with ``taken``, someone else now holds the seat."""
    _org(db, billing_notification_email="treasurer@club.example")
    slot, booking, receipt = _pending(db)
    expire_unpaid_seats(db, booking.payment_due_at + timedelta(seconds=1))
    assert (booking.status, receipt.status) == ("cancelled", "cancelled")
    if taken:
        service.create_booking(db, _member(db, 7), slot.id)
    return slot, booking, receipt


class TestWithASeatFree:
    def test_the_booking_is_given_back_and_the_money_kept(self, db):
        _, booking, receipt = _released(db)

        notify = record_late_payment(db, receipt, payment_method="stripe_checkout")

        assert receipt.status == "paid"
        assert booking.status == "booked"
        assert booking.refund_status == "none"
        assert booking.cancelled_at is None
        assert booking.cancelled_cause is None
        assert booking.late_payment_at is not None
        assert notify == [receipt.id]

    def test_the_club_is_alerted(self, db):
        _, booking, receipt = _released(db)
        db.commit()

        with patch(ALERT) as alert:
            record_late_payment(db, receipt, payment_method="stripe_checkout")
            db.commit()

        payload = alert.call_args.kwargs
        assert payload["to"] == "treasurer@club.example"
        assert payload["seat_confirmed"] is True
        assert "Court 1" in payload["seat_name"]


class TestWithoutOne:
    def test_the_money_is_owed_back_and_the_member_not_told_all_is_well(self, db):
        _, booking, receipt = _released(db, taken=True)

        notify = record_late_payment(db, receipt, payment_method="stripe_checkout")

        assert receipt.status == "paid"
        assert booking.status == "cancelled"
        assert booking.refund_status == "due"
        assert notify == []

    def test_a_slot_already_under_way_cannot_be_bought(self, db):
        slot, booking, receipt = _released(db)
        slot.slot_date = date.today() - timedelta(days=1)
        db.flush()

        record_late_payment(db, receipt, payment_method="stripe_checkout")

        assert booking.status == "cancelled"
        assert booking.refund_status == "due"

    def test_a_member_who_booked_the_slot_again_keeps_that_booking(self, db):
        slot, booking, receipt = _released(db)
        again = service.create_booking(db, booking.member, slot.id)

        record_late_payment(db, receipt, payment_method="stripe_checkout")

        assert booking.status == "cancelled"
        assert booking.refund_status == "due"
        assert again.status == "pending"


class TestThroughTheGateway:
    def test_the_stripe_webhook_records_it(self, client, db):
        _, booking, receipt = _released(db)
        _stripe_provider(db)

        resp = _post_stripe_paid(client, receipt, "late-booking")

        assert resp.status_code == 200, resp.text
        assert _reloaded(db, booking).status == "booked"
