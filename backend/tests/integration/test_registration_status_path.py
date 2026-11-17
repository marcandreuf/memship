"""One path for every status change, and the receipt side of each (#591).

The member cancelling and the organiser changing the status used to be two
paths, and only the first touched receipts. The first class here holds for
``legacy`` activities too, because it was a defect rather than a flow.
"""

from unittest.mock import patch

import pytest

from app.domains.activities.registration_service import (
    RegistrationError,
    admin_change_status,
    confirm_without_payment,
    register_member,
)
from app.domains.audit.models import AuditLog
from app.domains.billing.service import mark_receipt_paid
from tests.integration.test_pay_to_confirm_registration import (
    _assert_counters_match_rows,
)
from tests.integration.test_receipt_payment import _auth_cookie, _create_admin
from tests.integration.test_registration_billing import (
    _activity,
    _member,
    _receipts_for,
    membership_type,  # noqa: F401 — fixture
    org,  # noqa: F401 — fixture
)

PAY = "pay_to_confirm"


def _statuses(db, registration):
    return [r.status for r in _receipts_for(db, registration)]


class TestTheOrganiserMovesTheReceiptToo:
    @pytest.mark.parametrize("flow", ["legacy", PAY])
    def test_cancelling_voids_the_unpaid_receipt(self, db, org, membership_type, flow):
        activity, price = _activity(db, payment_flow=flow)
        registration = register_member(
            db, activity, _member(db, membership_type, f"c-{flow}"), price.id
        )

        admin_change_status(db, registration, "cancelled")

        assert _statuses(db, registration) == ["cancelled"]
        _assert_counters_match_rows(db, activity)

    def test_moving_a_confirmed_seat_to_the_waitlist_voids_its_receipt(
        self, db, org, membership_type
    ):
        activity, price = _activity(db, max_participants=2)
        registration = register_member(
            db, activity, _member(db, membership_type, "to-wait"), price.id
        )

        admin_change_status(db, registration, "waitlist")

        assert _statuses(db, registration) == ["cancelled"]
        _assert_counters_match_rows(db, activity)

    def test_a_paid_receipt_is_left_alone(self, db, org, membership_type):
        activity, price = _activity(db)
        registration = register_member(
            db, activity, _member(db, membership_type, "paid-kept"), price.id
        )
        mark_receipt_paid(db, _receipts_for(db, registration)[0], payment_method="cash")

        admin_change_status(db, registration, "cancelled")

        assert _statuses(db, registration) == ["paid"]

    def test_reconfirming_a_legacy_seat_bills_it_again(self, db, org, membership_type):
        activity, price = _activity(db)
        registration = register_member(
            db, activity, _member(db, membership_type, "again"), price.id
        )
        admin_change_status(db, registration, "cancelled")

        admin_change_status(db, registration, "confirmed")

        assert _statuses(db, registration) == ["cancelled", "emitted"]


class TestASeatThatNeedsPayment:
    def test_cannot_be_flipped_to_confirmed(self, db, org, membership_type):
        activity, price = _activity(db, payment_flow=PAY)
        registration = register_member(
            db, activity, _member(db, membership_type, "flip"), price.id
        )

        with pytest.raises(RegistrationError):
            admin_change_status(db, registration, "confirmed")
        assert registration.status == "pending"

    def test_back_from_the_waitlist_is_pending_with_a_new_receipt(
        self, db, org, membership_type
    ):
        activity, price = _activity(db, payment_flow=PAY, max_participants=1)
        register_member(db, activity, _member(db, membership_type, "seat"), price.id)
        waiting = register_member(
            db, activity, _member(db, membership_type, "waiting"), price.id
        )
        activity.max_participants = 2

        admin_change_status(db, waiting, "pending")

        assert waiting.status == "pending"
        [receipt] = _receipts_for(db, waiting)
        assert receipt.status == "emitted"
        assert receipt.is_batchable is False
        assert receipt.due_date is not None
        _assert_counters_match_rows(db, activity)

    def test_after_a_cancellation_it_owes_a_new_receipt(self, db, org, membership_type):
        activity, price = _activity(db, payment_flow=PAY)
        registration = register_member(
            db, activity, _member(db, membership_type, "re-pend"), price.id
        )
        admin_change_status(db, registration, "cancelled")

        admin_change_status(db, registration, "pending")

        assert _statuses(db, registration) == ["cancelled", "emitted"]

    def test_a_legacy_or_free_seat_cannot_be_pending(self, db, org, membership_type):
        activity, price = _activity(db)
        registration = register_member(
            db, activity, _member(db, membership_type, "no-pend"), price.id
        )

        with pytest.raises(RegistrationError):
            admin_change_status(db, registration, "pending")


class TestConfirmWithoutPayment:
    def test_confirms_and_cancels_the_receipt(self, db, org, membership_type):
        activity, price = _activity(db, payment_flow=PAY)
        registration = register_member(
            db, activity, _member(db, membership_type, "waive"), price.id
        )
        admin = _create_admin(db, "waive")

        confirm_without_payment(db, registration, admin.id)

        assert registration.status == "confirmed"
        assert registration.payment_due_at is None
        assert _statuses(db, registration) == ["cancelled"]
        _assert_counters_match_rows(db, activity)

    def test_is_recorded_in_the_audit_log(self, db, org, membership_type):
        activity, price = _activity(db, payment_flow=PAY)
        registration = register_member(
            db, activity, _member(db, membership_type, "waive-log"), price.id
        )
        admin = _create_admin(db, "waive-log")

        confirm_without_payment(db, registration, admin.id)

        entry = (
            db.query(AuditLog)
            .filter(
                AuditLog.table_name == "registrations",
                AuditLog.record_id == registration.id,
            )
            .one()
        )
        assert entry.user_id == admin.id
        assert entry.new_values["reason"] == "payment_waived"

    def test_only_a_pending_seat(self, db, org, membership_type):
        activity, price = _activity(db)
        registration = register_member(
            db, activity, _member(db, membership_type, "waive-no"), price.id
        )

        with pytest.raises(RegistrationError):
            confirm_without_payment(db, registration, None)

    def test_the_endpoint_takes_the_billing_key(self, client, db, org, membership_type):
        activity, price = _activity(db, payment_flow=PAY)
        member = _member(db, membership_type, "waive-ep")
        registration = register_member(db, activity, member, price.id)
        admin = _create_admin(db, "waive-ep")

        with patch("app.tasks.email_tasks.send_registration_email_task.delay"):
            resp = client.post(
                f"/api/v1/registrations/{registration.id}/confirm-without-payment",
                cookies=_auth_cookie(admin),
            )

        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "confirmed"
