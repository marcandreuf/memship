"""Paying a pending booking's receipt books it; the club can waive or cancel (#603)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.domains.audit.models import AuditLog
from app.domains.billing.models import Receipt
from app.domains.billing.service import create_credit_note, mark_receipt_paid
from app.domains.billing.schemas import CreditNoteCreate
from app.domains.bookings import service
from app.domains.bookings.models import Booking
from app.domains.organizations.models import OrganizationSettings
from tests.integration.api.v1.test_redsys_flow import (
    _create_redsys_provider,
    _post_webhook,
    _sign_notification,
)
from tests.integration.test_bookings_service import _member, _org
from tests.integration.test_pay_to_confirm_payment import (
    _post_stripe_paid,
    _stripe_provider,
)
from tests.integration.test_receipt_payment import _auth_cookie, _create_admin
from tests.integration.test_space_pay_to_confirm_booking import (
    Recorder,
    _receipts,
    _slot,
    _space,
)

BOOKING_MAIL = "app.tasks.email_tasks.send_booking_email_task.delay"


def _pending(db, i=0, *, capacity=1, **space_kwargs):
    slot = _slot(db, _space(db, **space_kwargs), capacity=capacity)
    booking = service.create_booking(db, _member(db, i), slot.id)
    assert booking.status == "pending"
    [receipt] = _receipts(db, booking)
    return slot, booking, receipt


def _reloaded(db, booking):
    db.expire_all()
    return db.query(Booking).filter(Booking.id == booking.id).one()


def _enable_bookings(db):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).one()
    org.features = {**(org.features or {}), "bookings": True}
    db.flush()


class TestPayingBooks:
    @pytest.mark.parametrize(
        "method", ["cash", "bank_transfer", "stripe_checkout", "redsys", "bizum"]
    )
    def test_every_method_books_it_the_same_way(self, db, method):
        _org(db)
        _, booking, receipt = _pending(db)

        mark_receipt_paid(db, receipt, payment_method=method)

        assert booking.status == "booked"
        assert booking.payment_due_at is None

    def test_the_confirmation_mail_waits_for_the_commit(self, db):
        _org(db)
        _, booking, receipt = _pending(db)
        db.commit()

        with patch(BOOKING_MAIL) as delay:
            mark_receipt_paid(db, receipt, payment_method="cash")
            delay.assert_not_called()
            db.commit()

        assert delay.call_args.kwargs["kind"] == "confirmation"

    def test_paying_a_legacy_receipt_changes_nothing(self, db):
        _org(db)
        slot = _slot(db, _space(db, flow="legacy"))
        booking = service.create_booking(db, _member(db), slot.id)
        [receipt] = _receipts(db, booking)
        db.commit()

        with patch(BOOKING_MAIL) as delay:
            mark_receipt_paid(db, receipt, payment_method="cash")
            db.commit()

        assert _reloaded(db, booking).status == "booked"
        delay.assert_not_called()


class TestEveryPaymentPathBooks:
    def test_marking_it_paid_by_hand(self, client, db):
        _org(db)
        _, booking, receipt = _pending(db)
        admin = _create_admin(db, "p2c-booking-by-hand")

        resp = client.post(
            f"/api/v1/receipts/{receipt.id}/pay",
            json={"payment_method": "bank_transfer"},
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 200, resp.text
        assert _reloaded(db, booking).status == "booked"

    def test_the_stripe_webhook(self, client, db):
        _org(db)
        _, booking, receipt = _pending(db, methods=("card",))
        _stripe_provider(db)

        resp = _post_stripe_paid(client, receipt, "p2c-booking")

        assert resp.status_code == 200, resp.text
        assert _reloaded(db, booking).status == "booked"

    def test_the_redsys_webhook(self, client, db):
        _org(db)
        _, booking, receipt = _pending(db, methods=("card",))
        receipt.redsys_ds_order = "000000603001"
        _create_redsys_provider(db)
        db.flush()

        resp = _post_webhook(
            client,
            _sign_notification(
                ds_order=receipt.redsys_ds_order,
                ds_amount=int(receipt.total_amount * 100),
            ),
        )

        assert resp.status_code == 200, resp.text
        assert _reloaded(db, booking).status == "booked"


class TestConfirmingWithoutPayment:
    def test_books_it_and_voids_the_receipt_on_the_record(self, db):
        _org(db)
        _, booking, receipt = _pending(db)
        admin = _create_admin(db, "p2c-booking-waive")

        service.confirm_booking_without_payment(db, booking, admin.id)

        assert booking.status == "booked"
        assert receipt.status == "cancelled"
        assert (
            db.query(AuditLog)
            .filter(AuditLog.table_name == "bookings", AuditLog.record_id == booking.id)
            .one()
            .new_values["reason"]
            == "payment_waived"
        )

    def test_is_only_for_a_pending_booking(self, db):
        _org(db)
        slot = _slot(db, _space(db, flow="legacy"))
        booking = service.create_booking(db, _member(db), slot.id)

        with pytest.raises(service.NotPending):
            service.confirm_booking_without_payment(db, booking, None)

    def test_needs_the_billing_permission(self, client, db):
        _org(db)
        _, booking, _ = _pending(db)
        admin = _create_admin(db, "p2c-booking-waive-api")
        _enable_bookings(db)

        resp = client.post(
            f"/api/v1/bookings/{booking.id}/confirm-without-payment",
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 204, resp.text
        assert _reloaded(db, booking).status == "booked"


def _admin_cancel(db, booking, notifier=None, **kwargs):
    return service.cancel_booking(
        db,
        booking,
        cancelled_by_user_id=None,
        is_admin=True,
        notifier=notifier,
        **kwargs,
    )


class TestCancelling:
    def test_a_pending_booking_voids_its_receipt_and_owes_nothing(self, db):
        _org(db)
        _, booking, receipt = _pending(db)

        _admin_cancel(db, booking)

        assert booking.status == "cancelled"
        assert receipt.status == "cancelled"
        assert booking.refund_status == "none"

    def test_a_paid_booking_is_owed_back_and_the_member_told(self, db):
        _org(db)
        _, booking, receipt = _pending(db)
        mark_receipt_paid(db, receipt, payment_method="cash")
        notifier = Recorder()

        _admin_cancel(db, booking, notifier)

        assert receipt.status == "paid"
        assert booking.refund_status == "due"
        [(kind, note)] = notifier.calls
        assert kind == "send_admin_cancellation"
        assert note.refund_due is True

    def test_the_club_may_keep_the_payment(self, db):
        _org(db)
        _, booking, receipt = _pending(db)
        mark_receipt_paid(db, receipt, payment_method="cash")

        _admin_cancel(db, booking, keep_payment=True)

        assert booking.refund_status == "none"

    def test_a_member_cannot_keep_their_own_payment_for_the_club(self, db):
        _org(db, booking_cancellation_deadline_minutes=0)
        _, booking, receipt = _pending(db)
        mark_receipt_paid(db, receipt, payment_method="cash")

        service.cancel_booking(
            db, booking, cancelled_by_user_id=None, is_admin=False, keep_payment=True
        )

        assert booking.refund_status == "due"

    def test_a_credit_note_on_the_booking_is_left_alone(self, db):
        _org(db)
        _, booking, receipt = _pending(db)
        note = create_credit_note(
            db, receipt, CreditNoteCreate(reason="Price corrected", amount=1), None
        )

        _admin_cancel(db, booking)

        assert receipt.status == "cancelled"
        assert note.status == "emitted"

    def test_cancelling_a_pending_booking_frees_its_seat(self, db):
        _org(db)
        slot, booking, _ = _pending(db, capacity=1)
        waiting = service.create_booking(db, _member(db, 9), slot.id)
        assert waiting.status == "waitlisted"

        _admin_cancel(db, booking)

        assert waiting.status != "waitlisted"


class TestAMemberReleasingTheirPendingBooking:
    def test_may_do_so_past_the_cancellation_notice(self, db):
        # The notice is a week; the slot is in three days.
        _org(db, booking_cancellation_deadline_minutes=10080)
        _, booking, _ = _pending(db)

        service.cancel_booking(db, booking, cancelled_by_user_id=None, is_admin=False)

        assert booking.status == "cancelled"

    def test_may_not_once_its_deadline_has_passed(self, db):
        _org(db)
        _, booking, _ = _pending(db)
        booking.payment_due_at = datetime.now(timezone.utc) - timedelta(minutes=1)

        with pytest.raises(service.CancellationTooLate):
            service.cancel_booking(
                db, booking, cancelled_by_user_id=None, is_admin=False
            )

    def test_my_bookings_offers_it(self, db):
        _org(db, booking_cancellation_deadline_minutes=10080)
        _, booking, _ = _pending(db)

        [row] = service.my_bookings(db, booking.party_id, scope="upcoming")

        assert row["status"] == "pending"
        assert row["can_cancel"] is True
