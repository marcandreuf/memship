"""What the screens read about a booking held until paid (#603)."""

from app.domains.billing.seats import BOOKING_SEAT_TEMPLATES
from tests.integration.test_bookings_service import _org
from tests.integration.test_pay_to_confirm_guard import _switch
from tests.integration.test_receipt_payment import _auth_cookie, _create_admin
from tests.integration.test_space_pay_to_confirm_payment import _pending


class TestTheSpaceForm:
    def test_is_told_what_it_may_offer(self, client, db):
        org = _org(db, booking_auto_cancel_enabled=True, booking_auto_cancel_hours=12)
        _switch(org, BOOKING_SEAT_TEMPLATES[:1])
        db.flush()

        resp = client.get(
            "/api/v1/spaces/payment-options",
            cookies=_auth_cookie(_create_admin(db, "space-options")),
        )

        assert resp.status_code == 200, resp.text
        assert resp.json() == {
            "usable_methods": ["cash"],
            "auto_cancel_enabled": True,
            "auto_cancel_hours": 12,
            "switched_off_templates": list(BOOKING_SEAT_TEMPLATES[1:]),
        }


class TestTheBookingsTab:
    def test_shows_the_deadline_and_the_receipt(self, client, db):
        _org(db)
        slot, booking, receipt = _pending(db)

        resp = client.get(
            f"/api/v1/spaces/{slot.space_id}/bookings?status=pending",
            cookies=_auth_cookie(_create_admin(db, "space-bookings-tab")),
        )

        assert resp.status_code == 200, resp.text
        [row] = resp.json()["items"]
        assert row["id"] == booking.id
        assert row["status"] == "pending"
        assert row["receipt_id"] == receipt.id
        assert row["receipt_status"] == "emitted"
        assert row["payment_due_at"] is not None
        assert row["refund_status"] == "none"
