"""Unit tests for Stripe provider adapter — mocked Stripe calls."""

from decimal import Decimal
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
