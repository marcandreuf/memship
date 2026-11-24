"""A slot or space whose bookings carry money cannot be deleted (#603).

Deleting cascades the bookings away, and with them whether the club owes a
refund. Paid bookings still to come, and cancelled ones with a refund due,
block the delete, forced or not; the club cancels them first or deactivates.
"""

from datetime import date, timedelta

import pytest

from app.domains.billing.service import mark_receipt_paid
from app.domains.bookings import service
from tests.integration.test_bookings_service import _member, _org
from tests.integration.test_receipt_payment import _auth_cookie, _create_admin
from tests.integration.test_space_pay_to_confirm_booking import Recorder, _receipts
from tests.integration.test_space_pay_to_confirm_payment import _admin_cancel, _pending


def _paid(db):
    slot, booking, receipt = _pending(db)
    mark_receipt_paid(db, receipt, payment_method="cash")
    return slot, booking, receipt


class TestRefused:
    @pytest.mark.parametrize("force", [False, True])
    def test_a_slot_with_a_paid_booking_to_come(self, db, force):
        _org(db)
        slot, _, _ = _paid(db)

        with pytest.raises(service.HasPaidBookings) as exc:
            service.delete_slot(db, slot, force=force)

        assert exc.value.fields == {"count": 1}

    def test_a_space_with_a_paid_booking_to_come(self, db):
        _org(db)
        slot, _, _ = _paid(db)

        with pytest.raises(service.HasPaidBookings):
            service.delete_space(db, slot.space, force=True)

    def test_a_slot_with_a_refund_still_owed(self, db):
        _org(db)
        slot, booking, _ = _paid(db)
        _admin_cancel(db, booking)
        assert booking.refund_status == "due"

        with pytest.raises(service.HasPaidBookings):
            service.delete_slot(db, slot)

    def test_through_the_api_with_a_code_the_screen_translates(self, client, db):
        _org(db)
        slot, _, _ = _paid(db)
        admin = _create_admin(db, "delete-paid-slot")

        resp = client.delete(
            f"/api/v1/spaces/{slot.space_id}/slots/{slot.id}?force=true",
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 422, resp.text
        assert resp.json()["detail"]["code"] == "has_paid_bookings"
        assert resp.json()["detail"]["count"] == 1


class TestAllowed:
    def test_a_pending_booking_is_cancelled_and_its_receipt_voided(self, db):
        _org(db)
        slot, booking, receipt = _pending(db)
        notifier = Recorder()

        service.delete_slot(db, slot, force=True, notifier=notifier)

        assert receipt.status == "cancelled"
        assert [kind for kind, _ in notifier.calls] == ["send_admin_cancellation"]

    def test_a_paid_booking_whose_slot_has_passed(self, db):
        _org(db)
        slot, _, _ = _paid(db)
        slot.slot_date = date.today() - timedelta(days=2)
        db.flush()

        service.delete_slot(db, slot)

    def test_a_refund_already_returned(self, db):
        _org(db)
        slot, booking, _ = _paid(db)
        _admin_cancel(db, booking)
        booking.refund_status = "returned"
        db.flush()

        service.delete_slot(db, slot)
