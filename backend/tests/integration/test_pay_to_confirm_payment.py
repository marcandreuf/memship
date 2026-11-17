"""Paying the receipt confirms the pending seat, whatever paid it (#591)."""

import json
from unittest.mock import patch

import pytest

from app.domains.activities.models import Registration
from app.domains.activities.registration_service import register_member
from app.domains.billing.models import PaymentProvider, Receipt
from app.domains.billing.service import mark_receipt_paid
from tests.integration.api.v1.test_redsys_flow import (
    _create_redsys_provider,
    _post_webhook,
    _sign_notification,
)
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

CONFIRMATION = "app.tasks.email_tasks.send_registration_email_task.delay"


def _pending(db, membership_type, suffix, **activity_kwargs):
    activity, price = _activity(db, payment_flow="pay_to_confirm", **activity_kwargs)
    registration = register_member(
        db, activity, _member(db, membership_type, suffix), price.id
    )
    assert registration.status == "pending"
    [receipt] = _receipts_for(db, registration)
    return activity, registration, receipt


def _reloaded(db, registration):
    db.expire_all()
    return db.query(Registration).filter(Registration.id == registration.id).one()


class TestPayingConfirms:
    @pytest.mark.parametrize(
        "method", ["cash", "bank_transfer", "stripe_checkout", "redsys", "bizum"]
    )
    def test_every_method_confirms_the_same_way(self, db, org, membership_type, method):
        activity, registration, receipt = _pending(db, membership_type, f"m-{method}")

        mark_receipt_paid(db, receipt, payment_method=method)

        assert registration.status == "confirmed"
        assert registration.payment_due_at is None
        _assert_counters_match_rows(db, activity)

    def test_the_confirmation_mail_waits_for_the_commit(self, db, org, membership_type):
        _, registration, receipt = _pending(db, membership_type, "mail")
        db.commit()

        with patch(CONFIRMATION) as delay:
            mark_receipt_paid(db, receipt, payment_method="cash")
            delay.assert_not_called()
            db.commit()

        assert delay.call_args.kwargs["status"] == "confirmed"

    def test_the_seat_stays_held_across_the_payment(self, db, org, membership_type):
        activity, registration, receipt = _pending(
            db, membership_type, "held", max_participants=1
        )

        mark_receipt_paid(db, receipt, payment_method="cash")

        db.refresh(activity)
        assert activity.current_participants == 1


class TestTheLegacyFlowIsUntouched:
    def test_paying_a_legacy_receipt_changes_nothing_on_the_registration(
        self, db, org, membership_type
    ):
        activity, price = _activity(db)
        registration = register_member(
            db, activity, _member(db, membership_type, "legacy-pay"), price.id
        )
        [receipt] = _receipts_for(db, registration)
        db.commit()

        with patch(CONFIRMATION) as delay:
            mark_receipt_paid(db, receipt, payment_method="cash")
            db.commit()

        assert _reloaded(db, registration).status == "confirmed"
        delay.assert_not_called()


class TestEveryPaymentPathConfirms:
    def test_marking_it_paid_by_hand(self, client, db, org, membership_type):
        _, registration, receipt = _pending(db, membership_type, "by-hand")
        admin = _create_admin(db, "p2c-by-hand")

        resp = client.post(
            f"/api/v1/receipts/{receipt.id}/pay",
            json={"payment_method": "bank_transfer"},
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 200, resp.text
        assert _reloaded(db, registration).status == "confirmed"

    def test_the_stripe_webhook(self, client, db, org, membership_type):
        from app.core.encryption import encrypt_config
        from app.domains.billing.providers.stripe_provider import StripeAdapter

        _, registration, receipt = _pending(db, membership_type, "stripe")
        db.add(
            PaymentProvider(
                provider_type="stripe",
                display_name="Stripe",
                status="active",
                config=encrypt_config(
                    {
                        "secret_key": "sk_test_p2c",
                        "publishable_key": "pk_test_p2c",
                        "webhook_secret": "whsec_p2c",
                    },
                    ["secret_key", "webhook_secret"],
                ),
                is_default=False,
            )
        )
        db.flush()
        payload = {
            "id": "evt_p2c_001",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_p2c",
                    "metadata": {"receipt_id": str(receipt.id)},
                    "payment_intent": "pi_p2c",
                }
            },
        }

        with patch.object(StripeAdapter, "verify_signature", return_value=payload):
            resp = client.post(
                "/api/v1/webhooks/stripe",
                content=json.dumps(payload).encode(),
                headers={
                    "content-type": "application/json",
                    "stripe-signature": "t=1,v1=fake",
                },
            )

        assert resp.status_code == 200, resp.text
        assert _reloaded(db, registration).status == "confirmed"

    def test_the_redsys_webhook(self, client, db, org, membership_type):
        _, registration, receipt = _pending(db, membership_type, "redsys")
        receipt.redsys_ds_order = "000000591001"
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
        db.expire_all()
        assert db.get(Receipt, receipt.id).status == "paid"
        assert _reloaded(db, registration).status == "confirmed"
