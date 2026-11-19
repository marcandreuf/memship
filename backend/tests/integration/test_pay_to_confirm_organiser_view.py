"""What the organiser sees and causes on a pay-to-confirm seat (#591 validation)."""

from unittest.mock import patch

from app.domains.activities.registration_service import (
    admin_change_status,
    register_member,
)
from app.domains.activities.schemas import ActivityUpdate
from app.domains.activities.service import update_activity
from app.domains.billing.seats import SEAT_PAYMENT_TEMPLATES
from tests.integration.test_pay_to_confirm_guard import _switch
from tests.integration.test_pay_to_confirm_registration import _auto_cancel
from tests.integration.test_receipt_payment import _auth_cookie, _create_admin
from tests.integration.test_registration_billing import (
    _activity,
    _member,
    _receipts_for,
    membership_type,  # noqa: F401 — fixture
    org,  # noqa: F401 — fixture
)

PAY = "pay_to_confirm"
PENDING_MAIL = "app.tasks.email_tasks.send_pending_payment_email_task.delay"
CANCELLED_MAIL = "app.tasks.email_tasks.send_cancellation_email_task.delay"


def _held(db, membership_type, suffix):
    activity, price = _activity(db, payment_flow=PAY, max_participants=5)
    registration = register_member(db, activity, _member(db, membership_type, suffix), price.id)
    assert registration.status == "pending"
    return activity, registration


class TestTheRegistrationList:
    def test_rows_carry_the_amounts(self, client, db, org, membership_type):
        # Without them the screen offered "Confirmed" on a seat that owes money.
        activity, registration = _held(db, membership_type, "ov-list")
        admin = _create_admin(db, "ov-list")
        db.commit()

        resp = client.get(
            f"/api/v1/activities/{activity.id}/registrations/", cookies=_auth_cookie(admin)
        )

        assert resp.status_code == 200, resp.text
        [row] = resp.json()["items"]
        assert row["discounted_amount"] == float(registration.discounted_amount)
        assert row["total_amount"] > row["discounted_amount"] or row["vat_rate"] == 0

    def test_confirming_by_hand_is_refused_with_a_code(self, client, db, org, membership_type):
        _, registration = _held(db, membership_type, "ov-code")
        admin = _create_admin(db, "ov-code")
        db.commit()

        resp = client.put(
            f"/api/v1/registrations/{registration.id}/status",
            json={"status": "confirmed"},
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "seat_needs_payment"


class TestCancellingFromThePanel:
    def test_tells_the_member(self, db, org, membership_type):
        _, registration = _held(db, membership_type, "ov-cancel")

        with patch(CANCELLED_MAIL) as delay:
            admin_change_status(db, registration, "cancelled")
            db.commit()

        delay.assert_called_once()


class TestSwitchingAutoCancelOnLater:
    def test_the_activity_gives_pending_seats_a_deadline_and_says_so(
        self, db, org, membership_type
    ):
        _switch(org, SEAT_PAYMENT_TEMPLATES)
        activity, registration = _held(db, membership_type, "ov-late-act")
        assert registration.payment_due_at is None
        [receipt] = _receipts_for(db, registration)
        with patch(PENDING_MAIL):
            db.commit()  # the registration's own pending mail goes here

        with patch(PENDING_MAIL) as delay:
            update_activity(
                db, activity, ActivityUpdate(auto_cancel_enabled=True, auto_cancel_hours=24)
            )
            db.commit()

        assert registration.payment_due_at is not None
        assert receipt.due_date <= registration.payment_due_at.date()
        delay.assert_called_once()
        assert delay.call_args.kwargs["deadline"]
        # Not the first mail again: it says a deadline now applies.
        assert delay.call_args.kwargs["deadline_added"] is True

    def test_the_club_default_reaches_activities_that_follow_it(
        self, client, db, org, membership_type
    ):
        _switch(org, SEAT_PAYMENT_TEMPLATES)
        activity, registration = _held(db, membership_type, "ov-late-club")
        admin = _create_admin(db, "ov-late-club")
        db.commit()

        with patch(PENDING_MAIL):
            resp = client.put(
                "/api/v1/settings/",
                json={"features": {"activity_auto_cancel_enabled": True}},
                cookies=_auth_cookie(admin),
            )

        assert resp.status_code == 200, resp.text
        db.expire_all()
        db.refresh(registration)
        assert registration.payment_due_at is not None

    def test_a_seat_that_already_has_a_deadline_keeps_it(self, db, org, membership_type):
        _auto_cancel(org, hours=48)
        activity, registration = _held(db, membership_type, "ov-keep")
        due = registration.payment_due_at
        assert due is not None

        update_activity(db, activity, ActivityUpdate(auto_cancel_hours=2))

        assert registration.payment_due_at == due
