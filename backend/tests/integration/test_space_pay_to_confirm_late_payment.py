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
from tests.integration.test_receipt_payment import _auth_cookie, _create_admin
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


class TestTheClubsLists:
    """Bookings and registrations share one refund list and one banner."""

    def test_a_booking_owed_back_is_listed_with_its_space(self, client, db):
        slot, booking, receipt = _released(db, taken=True)
        record_late_payment(db, receipt, payment_method="stripe_checkout")
        cookies = _auth_cookie(_create_admin(db, "seat-lists"))

        refunds = client.get("/api/v1/seats/refunds", cookies=cookies).json()["items"]
        banner = client.get("/api/v1/seats/late-payments", cookies=cookies).json()["items"]

        [refund] = [i for i in refunds if (i["kind"], i["seat_id"]) == ("booking", booking.id)]
        assert refund["owner_id"] == slot.space_id
        assert "Court 1" in refund["owner_name"]
        assert refund["receipt_number"] == receipt.receipt_number
        assert ("booking", booking.id) in [(i["kind"], i["seat_id"]) for i in banner]

    def test_the_club_marks_it_returned_and_seen(self, client, db):
        _, booking, receipt = _released(db, taken=True)
        record_late_payment(db, receipt, payment_method="stripe_checkout")
        cookies = _auth_cookie(_create_admin(db, "seat-actions"))

        returned = client.post(
            f"/api/v1/seats/booking/{booking.id}/refund-returned", cookies=cookies
        )
        seen = client.post(
            f"/api/v1/seats/booking/{booking.id}/late-payment-seen", cookies=cookies
        )

        assert returned.status_code == 200, returned.text
        assert seen.status_code == 204, seen.text
        db.expire_all()
        assert booking.refund_status == "returned"
        assert booking.late_payment_seen_at is not None

    def test_an_unknown_kind_is_refused(self, client, db):
        _org(db)
        resp = client.post(
            "/api/v1/seats/membership/1/late-payment-seen",
            cookies=_auth_cookie(_create_admin(db, "seat-kind")),
        )

        assert resp.status_code == 422
