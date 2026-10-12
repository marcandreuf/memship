"""Unit tests for Stripe provider adapter — mocked Stripe calls."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.domains.billing.providers.stripe_provider import (
    StripeAdapter,
    to_minor_units,
)


class TestMinorUnits:
    def test_eur_to_cents(self):
        assert to_minor_units(Decimal("10.50"), "EUR") == 1050

    def test_eur_whole_amount(self):
        assert to_minor_units(Decimal("100.00"), "EUR") == 10000

    def test_jpy_no_decimals(self):
        assert to_minor_units(Decimal("1000"), "JPY") == 1000

    def test_krw_no_decimals(self):
        assert to_minor_units(Decimal("50000"), "KRW") == 50000

    def test_usd_to_cents(self):
        assert to_minor_units(Decimal("25.99"), "USD") == 2599

    def test_case_insensitive(self):
        assert to_minor_units(Decimal("100"), "jpy") == 100


class TestCreatePayment:
    """Builds the Checkout session, and nothing else ran this.

    Every other test of the Stripe payment path patches ``create_payment``
    out — the endpoint tests mock the adapter, so the params this assembles
    were never executed. A wrong ``unit_amount`` charges the member the wrong
    sum, and a missing ``metadata.receipt_id`` leaves the webhook with no
    receipt to mark paid: both are silent here and visible only to whoever
    pays.
    """

    def _adapter(self):
        return StripeAdapter({"secret_key": "sk_test", "webhook_secret": "whsec_test"})

    def _call(self, *, currency="EUR", total="50.00", stripe_customer_id=None):
        """Run create_payment against a mocked SDK; return (params, result)."""
        receipt = SimpleNamespace(
            id=42,
            receipt_number="2026-0042",
            description="Cuota anual 2026",
            total_amount=Decimal(total),
        )
        person = SimpleNamespace(email="member@example.test")

        with patch(
            "app.domains.billing.providers.stripe_provider.stripe.StripeClient"
        ) as client_cls:
            sessions = client_cls.return_value.v1.checkout.sessions
            sessions.create.return_value = MagicMock(
                url="https://checkout.stripe.com/c/pay/cs_test_123", id="cs_test_123"
            )
            result = self._adapter().create_payment(
                receipt=receipt,
                person=person,
                currency=currency,
                success_url="https://example.test/ok",
                cancel_url="https://example.test/ko",
                stripe_customer_id=stripe_customer_id,
            )
            params = sessions.create.call_args.kwargs["params"]
        return params, result

    def test_builds_a_one_off_payment_for_the_receipt_total(self):
        params, _ = self._call(total="50.00")

        assert params["mode"] == "payment"
        assert params["success_url"] == "https://example.test/ok"
        assert params["cancel_url"] == "https://example.test/ko"

        (item,) = params["line_items"]
        assert item["quantity"] == 1
        assert item["price_data"]["unit_amount"] == 5000
        assert item["price_data"]["product_data"]["name"] == "Cuota anual 2026"

    def test_metadata_carries_what_the_webhook_needs_to_find_the_receipt(self):
        params, _ = self._call()

        # `handle_webhook` reads `metadata.receipt_id` to locate the receipt, and
        # Stripe stores metadata as strings.
        assert params["metadata"] == {"receipt_id": "42", "receipt_number": "2026-0042"}
        assert isinstance(params["metadata"]["receipt_id"], str)

    def test_currency_is_lowercased_for_stripe(self):
        params, _ = self._call(currency="EUR")

        assert params["line_items"][0]["price_data"]["currency"] == "eur"

    def test_a_zero_decimal_currency_is_not_scaled(self):
        """JPY has no minor unit, so scaling it would charge 100x."""
        params, _ = self._call(currency="JPY", total="1000")

        assert params["line_items"][0]["price_data"]["unit_amount"] == 1000

    def test_a_known_stripe_customer_is_passed_as_the_customer(self):
        params, _ = self._call(stripe_customer_id="cus_abc123")

        assert params["customer"] == "cus_abc123"
        assert "customer_email" not in params, "both would conflict at Stripe"

    def test_without_a_stripe_customer_the_email_is_sent_instead(self):
        params, _ = self._call(stripe_customer_id=None)

        assert params["customer_email"] == "member@example.test"
        assert "customer" not in params

    def test_returns_the_session_url_and_id(self):
        _, result = self._call()

        assert result == {
            "redirect_url": "https://checkout.stripe.com/c/pay/cs_test_123",
            "session_id": "cs_test_123",
        }


class TestVerifySignature:
    def test_missing_header_raises(self):
        adapter = StripeAdapter({"secret_key": "sk_test", "webhook_secret": "whsec_test"})
        with pytest.raises(ValueError, match="Missing Stripe-Signature"):
            adapter.verify_signature({}, b"{}")

    @patch("app.domains.billing.providers.stripe_provider.stripe.Webhook.construct_event")
    def test_valid_signature(self, mock_construct):
        mock_construct.return_value = {"id": "evt_123", "type": "checkout.session.completed"}
        adapter = StripeAdapter({"secret_key": "sk_test", "webhook_secret": "whsec_test"})
        result = adapter.verify_signature(
            {"stripe-signature": "t=123,v1=abc"},
            b'{"id":"evt_123"}',
        )
        assert result["id"] == "evt_123"
        mock_construct.assert_called_once()

    @patch("app.domains.billing.providers.stripe_provider.stripe.Webhook.construct_event")
    def test_returns_plain_dict_even_when_sdk_returns_stripe_object(self, mock_construct):
        # Regression: the real SDK returns a StripeObject whose __getattr__ routes
        # `.get` as a key lookup, breaking downstream `event_data.get(...)` calls.
        # The adapter must hand back a plain dict at the boundary.
        import stripe

        mock_construct.return_value = stripe.convert_to_stripe_object(
            {
                "id": "evt_regress",
                "type": "checkout.session.completed",
                "data": {"object": {"metadata": {"receipt_id": "42"}}},
            }
        )
        adapter = StripeAdapter({"secret_key": "sk_test", "webhook_secret": "whsec_test"})
        result = adapter.verify_signature(
            {"stripe-signature": "t=123,v1=abc"},
            b'{"id":"evt_regress","type":"checkout.session.completed","data":{"object":{"metadata":{"receipt_id":"42"}}}}',
        )
        assert type(result) is dict
        assert result.get("id") == "evt_regress"
        assert result["data"]["object"].get("metadata", {}).get("receipt_id") == "42"


class TestExtractors:
    def test_extract_event_id(self):
        adapter = StripeAdapter({"secret_key": "sk_test", "webhook_secret": "whsec_test"})
        assert adapter.extract_event_id({"id": "evt_abc"}) == "evt_abc"

    def test_extract_event_type(self):
        adapter = StripeAdapter({"secret_key": "sk_test", "webhook_secret": "whsec_test"})
        assert adapter.extract_event_type({"type": "checkout.session.completed"}) == "checkout.session.completed"


class TestHandleWebhook:
    def _adapter(self):
        return StripeAdapter({"secret_key": "sk_test", "webhook_secret": "whsec_test"})

    def test_unhandled_event_ignored(self):
        adapter = self._adapter()
        db = MagicMock()
        result = adapter.handle_webhook(db, {"type": "customer.created", "data": {"object": {}}})
        assert result["ignored"] is True

    def test_checkout_completed_no_receipt_id_ignored(self):
        adapter = self._adapter()
        db = MagicMock()
        result = adapter.handle_webhook(db, {
            "type": "checkout.session.completed",
            "data": {"object": {"metadata": {}}},
        })
        assert result["ignored"] is True

    def test_checkout_completed_marks_paid(self):
        adapter = self._adapter()
        db = MagicMock()
        receipt = MagicMock()
        receipt.id = 42
        receipt.status = "emitted"
        db.query.return_value.filter.return_value.first.return_value = receipt

        result = adapter.handle_webhook(db, {
            "type": "checkout.session.completed",
            "data": {"object": {
                "metadata": {"receipt_id": "42"},
                "payment_intent": "pi_abc123",
            }},
        })

        assert result["receipt_id"] == 42
        assert receipt.status == "paid"
        assert receipt.payment_method == "stripe_checkout"
        assert receipt.stripe_payment_intent_id == "pi_abc123"

    def test_checkout_completed_already_paid_ignored(self):
        adapter = self._adapter()
        db = MagicMock()
        receipt = MagicMock()
        receipt.id = 42
        receipt.status = "paid"
        db.query.return_value.filter.return_value.first.return_value = receipt

        result = adapter.handle_webhook(db, {
            "type": "checkout.session.completed",
            "data": {"object": {"metadata": {"receipt_id": "42"}}},
        })

        assert result["ignored"] is True

    def test_checkout_expired_marks_returned(self):
        adapter = self._adapter()
        db = MagicMock()
        receipt = MagicMock()
        receipt.id = 42
        receipt.status = "emitted"
        db.query.return_value.filter.return_value.first.return_value = receipt

        result = adapter.handle_webhook(db, {
            "type": "checkout.session.expired",
            "data": {"object": {"metadata": {"receipt_id": "42"}}},
        })

        assert result["receipt_id"] == 42
        assert receipt.status == "returned"
        assert "expired" in receipt.return_reason.lower()

    def test_checkout_expired_already_returned_ignored(self):
        adapter = self._adapter()
        db = MagicMock()
        receipt = MagicMock()
        receipt.id = 42
        receipt.status = "returned"
        db.query.return_value.filter.return_value.first.return_value = receipt

        result = adapter.handle_webhook(db, {
            "type": "checkout.session.expired",
            "data": {"object": {"metadata": {"receipt_id": "42"}}},
        })

        assert result["ignored"] is True


class TestAmountVerification:
    """An authorised session is not proof it paid what we asked.

    The signature proves Stripe sent the message, not that the sum is right, so
    a partial capture or a mismatched amount used to be recorded as payment in
    full.
    """

    def _adapter(self):
        return StripeAdapter({"secret_key": "sk_test", "webhook_secret": "whsec_test"})

    def _receipt(self, total="50.00", status="emitted"):
        receipt = MagicMock()
        receipt.id = 42
        receipt.status = status
        receipt.total_amount = Decimal(total)
        return receipt

    def _completed(self, adapter, db, **obj):
        return adapter.handle_webhook(
            db,
            {
                "type": "checkout.session.completed",
                "data": {"object": {"metadata": {"receipt_id": "42"}, **obj}},
            },
        )

    def test_short_payment_does_not_mark_paid(self):
        adapter, db = self._adapter(), MagicMock()
        receipt = self._receipt(total="50.00")
        db.query.return_value.filter.return_value.first.return_value = receipt

        result = self._completed(
            adapter, db, amount_total=1000, currency="eur"  # 10.00, not 50.00
        )

        assert result["ignored"] is True
        assert "mismatch" in result["reason"].lower()
        assert receipt.status == "emitted", "a short payment was recorded as paid"

    def test_matching_amount_still_pays(self):
        adapter, db = self._adapter(), MagicMock()
        receipt = self._receipt(total="50.00")
        db.query.return_value.filter.return_value.first.return_value = receipt

        result = self._completed(
            adapter, db, amount_total=5000, currency="eur", payment_intent="pi_ok"
        )

        assert result.get("ignored") is not True
        assert receipt.status == "paid"

    def test_overpayment_is_also_a_mismatch(self):
        """Not just a shortfall — any disagreement needs a person."""
        adapter, db = self._adapter(), MagicMock()
        receipt = self._receipt(total="50.00")
        db.query.return_value.filter.return_value.first.return_value = receipt

        result = self._completed(adapter, db, amount_total=9900, currency="eur")

        assert result["ignored"] is True
        assert receipt.status == "emitted"

    def test_absent_amount_is_not_a_mismatch(self):
        """Nothing to compare must not become a new way to reject a payment."""
        adapter, db = self._adapter(), MagicMock()
        receipt = self._receipt(total="50.00")
        db.query.return_value.filter.return_value.first.return_value = receipt

        result = self._completed(adapter, db, payment_intent="pi_ok")

        assert result.get("ignored") is not True
        assert receipt.status == "paid"

    def test_zero_decimal_currency_is_not_scaled(self):
        """JPY has no minor unit, so 5000 yen is amount_total 5000."""
        adapter, db = self._adapter(), MagicMock()
        receipt = self._receipt(total="5000")
        db.query.return_value.filter.return_value.first.return_value = receipt

        result = self._completed(
            adapter, db, amount_total=5000, currency="jpy", payment_intent="pi_ok"
        )

        assert result.get("ignored") is not True
        assert receipt.status == "paid"
