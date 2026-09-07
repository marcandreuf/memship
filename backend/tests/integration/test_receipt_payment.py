"""Every payment path lands in ``mark_receipt_paid``, and notifies after commit."""

import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.billing.models import PaymentProvider, Receipt
from app.domains.billing.service import (
    dispatch_payment_notifications,
    mark_receipt_paid,
    mark_receipts_paid,
)
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person

FANOUT = "app.tasks.billing_tasks.payment_notifications_fanout.delay"


# --- Fixtures ---


def _create_org(db):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if org:
        return org
    org = OrganizationSettings(
        id=1,
        name="Test Club",
        currency="EUR",
        invoice_prefix="FAC",
        invoice_annual_reset=True,
        default_vat_rate=Decimal("21.00"),
    )
    db.add(org)
    db.flush()
    return org


def _create_member(db, suffix):
    person = Person(
        first_name="Pay",
        last_name=f"Test-{suffix}",
        email=f"{suffix}@pay-test.example",
    )
    db.add(person)
    db.flush()
    mtype = MembershipType(
        name=f"Standard-{suffix}",
        slug=f"standard-{suffix}",
        base_price=Decimal("100.00"),
        billing_frequency="monthly",
    )
    db.add(mtype)
    db.flush()
    member = Member(
        person_id=person.id,
        membership_type_id=mtype.id,
        member_number=f"MP-{suffix}",
        status="active",
        joined_at=date(2026, 1, 1),
        is_active=True,
    )
    db.add(member)
    db.flush()
    return member


def _create_receipt(db, member, suffix, status="emitted"):
    _create_org(db)
    receipt = Receipt(
        receipt_number=f"FAC-2026-PAY-{suffix}",
        member_id=member.id,
        origin="membership",
        description="Membership fee",
        base_amount=Decimal("100.00"),
        vat_rate=Decimal("21.00"),
        vat_amount=Decimal("21.00"),
        total_amount=Decimal("121.00"),
        status=status,
        emission_date=date(2026, 4, 1),
        is_active=True,
    )
    db.add(receipt)
    db.flush()
    return receipt


def _create_admin(db, suffix):
    person = Person(
        first_name="Admin",
        last_name=f"Pay-{suffix}",
        email=f"admin-{suffix}@pay-test.example",
    )
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=person.email,
        password_hash=hash_password("password123"),
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id)}


# --- The shared function ---


class TestMarkReceiptPaid:
    def test_manual_payment_records_method_and_date(self, db):
        member = _create_member(db, "manual")
        receipt = _create_receipt(db, member, "manual")

        pending = mark_receipt_paid(
            db,
            receipt,
            payment_method="cash",
            payment_date=date(2026, 4, 15),
        )

        assert pending == [receipt.id]
        assert receipt.status == "paid"
        assert receipt.payment_method == "cash"
        assert receipt.payment_date == date(2026, 4, 15)

    def test_payment_date_defaults_to_today(self, db):
        member = _create_member(db, "today")
        receipt = _create_receipt(db, member, "today")

        mark_receipt_paid(db, receipt, payment_method="bank_transfer")

        assert receipt.payment_date == date.today()

    def test_stripe_fields_are_recorded(self, db):
        member = _create_member(db, "stripe")
        receipt = _create_receipt(db, member, "stripe")

        mark_receipt_paid(
            db,
            receipt,
            payment_method="stripe_checkout",
            transaction_id="pi_abc",
            stripe_payment_intent_id="pi_abc",
        )

        assert receipt.payment_method == "stripe_checkout"
        assert receipt.stripe_payment_intent_id == "pi_abc"
        assert receipt.transaction_id == "pi_abc"

    def test_redsys_fields_are_recorded(self, db):
        member = _create_member(db, "redsys")
        receipt = _create_receipt(db, member, "redsys")

        mark_receipt_paid(
            db,
            receipt,
            payment_method="redsys",
            transaction_id="AUTH999",
            redsys_auth_code="AUTH999",
        )

        assert receipt.payment_method == "redsys"
        assert receipt.redsys_auth_code == "AUTH999"
        assert receipt.transaction_id == "AUTH999"

    def test_bizum_survives_a_redsys_notification(self, db):
        """Redsys only knows the money came through it; initiate knew it was Bizum."""
        member = _create_member(db, "bizum")
        receipt = _create_receipt(db, member, "bizum")
        receipt.payment_method = "bizum"
        db.flush()

        mark_receipt_paid(db, receipt, payment_method="redsys")

        assert receipt.payment_method == "bizum"

    def test_paying_twice_is_a_no_op(self, db):
        """Both webhook paths can deliver the same payment twice."""
        member = _create_member(db, "twice")
        receipt = _create_receipt(db, member, "twice")

        first = mark_receipt_paid(
            db, receipt, payment_method="cash", payment_date=date(2026, 4, 15)
        )
        second = mark_receipt_paid(
            db,
            receipt,
            payment_method="stripe_checkout",
            payment_date=date(2026, 5, 1),
            stripe_payment_intent_id="pi_late",
        )

        assert first == [receipt.id]
        assert second == []
        assert receipt.payment_method == "cash"
        assert receipt.payment_date == date(2026, 4, 15)
        assert receipt.stripe_payment_intent_id is None

    def test_a_cancelled_receipt_cannot_be_paid(self, db):
        member = _create_member(db, "cancelled")
        receipt = _create_receipt(db, member, "cancelled", status="cancelled")

        with pytest.raises(HTTPException) as exc:
            mark_receipt_paid(db, receipt, payment_method="cash")

        assert exc.value.status_code == 400


class TestMarkReceiptsPaid:
    def test_the_whole_batch_is_marked_and_returned(self, db):
        member = _create_member(db, "bulk")
        receipts = [_create_receipt(db, member, f"bulk-{i}") for i in range(3)]

        pending = mark_receipts_paid(
            db,
            receipts,
            payment_method="direct_debit",
            payment_date=date(2026, 5, 5),
        )

        assert pending == [r.id for r in receipts]
        assert all(r.status == "paid" for r in receipts)
        assert all(r.payment_method == "direct_debit" for r in receipts)
        assert all(r.payment_date == date(2026, 5, 5) for r in receipts)

    def test_an_already_paid_receipt_is_skipped(self, db):
        member = _create_member(db, "bulk-dup")
        already = _create_receipt(db, member, "bulk-dup-0")
        fresh = _create_receipt(db, member, "bulk-dup-1")
        mark_receipt_paid(db, already, payment_method="cash")

        pending = mark_receipts_paid(
            db, [already, fresh], payment_method="direct_debit"
        )

        assert pending == [fresh.id]
        assert already.payment_method == "cash"


# --- Dispatch ---


class TestDispatchPaymentNotifications:
    def test_one_fanout_job_covers_the_whole_batch(self):
        with patch(FANOUT) as delay:
            dispatch_payment_notifications([1, 2, 3])

        delay.assert_called_once_with([1, 2, 3])

    def test_nothing_to_notify_enqueues_nothing(self):
        with patch(FANOUT) as delay:
            dispatch_payment_notifications([])

        delay.assert_not_called()

    def test_a_broker_failure_does_not_propagate(self):
        """The payment is already recorded — dispatch must not undo it."""
        with patch(FANOUT, side_effect=RuntimeError("broker down")):
            dispatch_payment_notifications([1])

    def test_the_fanout_queues_one_task_per_receipt(self):
        from app.tasks.billing_tasks import payment_notifications_fanout

        with patch("app.tasks.billing_tasks.send_payment_notification.delay") as delay:
            queued = payment_notifications_fanout([7, 8])

        assert queued == 2
        assert [call.args[0] for call in delay.call_args_list] == [7, 8]


class TestThePaymentConfirmation:
    """What the fanned-out task actually sends, once a club has switched it on."""

    def _paid(self, db, suffix, method="direct_debit"):
        member = _create_member(db, suffix)
        receipt = _create_receipt(db, member, suffix)
        mark_receipt_paid(
            db, receipt, payment_method=method, payment_date=date(2026, 4, 15)
        )
        return receipt

    def test_it_tells_the_member_the_amount_the_concept_and_the_date(self, db):
        from app.tasks.billing_tasks import _send_payment_confirmation

        receipt = self._paid(db, "conf-body")

        with patch("app.core.email._template_enabled", return_value=True), patch(
            "app.core.email.send_email", return_value=True
        ) as send:
            assert _send_payment_confirmation(db, receipt.id) is True

        to, subject, html = send.call_args[0]
        assert to == "conf-body@pay-test.example"
        assert receipt.receipt_number in subject
        assert "Membership fee" in html
        assert "121.00 EUR" in html
        assert "2026-04-15" in html

    def test_a_direct_debit_says_so(self, db):
        """The case with no other signal: the label is the reassurance."""
        from app.tasks.billing_tasks import _send_payment_confirmation

        receipt = self._paid(db, "conf-sepa")

        with patch("app.core.email._template_enabled", return_value=True), patch(
            "app.core.email.send_email", return_value=True
        ) as send:
            _send_payment_confirmation(db, receipt.id)

        assert "Domiciliación bancaria" in send.call_args[0][2]

    def test_a_checkout_payment_leaves_the_method_row_out(self, db):
        from app.tasks.billing_tasks import _send_payment_confirmation

        receipt = self._paid(db, "conf-stripe", method="stripe_checkout")

        with patch("app.core.email._template_enabled", return_value=True), patch(
            "app.core.email.send_email", return_value=True
        ) as send:
            _send_payment_confirmation(db, receipt.id)

        html = send.call_args[0][2]
        assert "stripe_checkout" not in html
        assert "Forma de pago" not in html

    def test_nothing_is_sent_without_an_address(self, db):
        from app.tasks.billing_tasks import _send_payment_confirmation

        receipt = self._paid(db, "conf-noaddr")
        member = db.query(Member).filter(Member.id == receipt.member_id).first()
        db.query(Person).filter(Person.id == member.person_id).first().email = None
        db.flush()

        with patch("app.core.email.send_email") as send:
            assert _send_payment_confirmation(db, receipt.id) is False
        send.assert_not_called()

    def test_an_unknown_receipt_is_not_a_failure(self, db):
        from app.tasks.billing_tasks import _send_payment_confirmation

        with patch("app.core.email.send_email") as send:
            assert _send_payment_confirmation(db, 999_999) is False
        send.assert_not_called()

    def test_an_untouched_install_sends_nothing(self, db):
        """Default-off: the catalogue entry alone mails nobody."""
        from app.tasks.billing_tasks import _send_payment_confirmation

        receipt = self._paid(db, "conf-off")

        with patch("app.core.email.send_email") as send:
            assert _send_payment_confirmation(db, receipt.id) is False
        send.assert_not_called()


# --- The three write sites ---


class TestManualPaymentEndpoint:
    def test_paying_by_hand_notifies_after_the_commit(self, client, db):
        member = _create_member(db, "ep-pay")
        receipt = _create_receipt(db, member, "ep-pay")
        admin = _create_admin(db, "ep-pay")

        with patch(FANOUT) as delay:
            resp = client.post(
                f"/api/v1/receipts/{receipt.id}/pay",
                json={"payment_method": "cash", "payment_date": "2026-04-15"},
                cookies=_auth_cookie(admin),
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "paid"
        delay.assert_called_once_with([receipt.id])

    def test_a_rejected_payment_notifies_nothing(self, client, db):
        """The transaction never commits, so no notification may go out."""
        member = _create_member(db, "ep-bad")
        receipt = _create_receipt(db, member, "ep-bad", status="new")
        admin = _create_admin(db, "ep-bad")

        with patch(FANOUT) as delay:
            resp = client.post(
                f"/api/v1/receipts/{receipt.id}/pay",
                json={"payment_method": "cash"},
                cookies=_auth_cookie(admin),
            )

        assert resp.status_code == 400
        delay.assert_not_called()
        db.refresh(receipt)
        assert receipt.status == "new"


class TestStripeWebhookNotifies:
    def _provider(self, db):
        from app.core.encryption import encrypt_config

        provider = PaymentProvider(
            provider_type="stripe",
            display_name="Stripe",
            status="active",
            config=encrypt_config(
                {
                    "secret_key": "sk_test_abc",
                    "publishable_key": "pk_test_abc",
                    "webhook_secret": "whsec_abc",
                },
                ["secret_key", "webhook_secret"],
            ),
            is_default=False,
        )
        db.add(provider)
        db.flush()
        return provider

    def _post(self, client, payload):
        from app.domains.billing.providers.stripe_provider import StripeAdapter

        with patch.object(StripeAdapter, "verify_signature", return_value=payload):
            return client.post(
                "/api/v1/webhooks/stripe",
                content=json.dumps(payload).encode(),
                headers={
                    "content-type": "application/json",
                    "stripe-signature": "t=1,v1=fake",
                },
            )

    def test_a_redelivered_webhook_notifies_once(self, client, db):
        member = _create_member(db, "wh-dup")
        receipt = _create_receipt(db, member, "wh-dup")
        self._provider(db)

        payload = {
            "id": "evt_notify_dup_001",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_notify_dup",
                    "metadata": {"receipt_id": str(receipt.id)},
                    "payment_intent": "pi_notify_dup",
                }
            },
        }

        with patch(FANOUT) as delay:
            first = self._post(client, payload)
            second = self._post(client, payload)

        assert first.status_code == 200
        assert second.status_code == 200
        delay.assert_called_once_with([receipt.id])

        db.expire_all()
        receipt = db.query(Receipt).filter(Receipt.id == receipt.id).first()
        assert receipt.status == "paid"
        assert receipt.payment_method == "stripe_checkout"

    def test_an_ignored_event_notifies_nothing(self, client, db):
        member = _create_member(db, "wh-ign")
        receipt = _create_receipt(db, member, "wh-ign", status="cancelled")
        self._provider(db)

        payload = {
            "id": "evt_notify_ign_001",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_notify_ign",
                    "metadata": {"receipt_id": str(receipt.id)},
                    "payment_intent": "pi_notify_ign",
                }
            },
        }

        with patch(FANOUT) as delay:
            resp = self._post(client, payload)

        assert resp.status_code == 200
        delay.assert_not_called()
