"""Stripe payment provider adapter — Checkout flow.

Implements PaymentProviderAdapter for Stripe Checkout sessions.
Invoice flow (Send via Stripe) deferred to v0.4.5.
"""

import logging
from datetime import date
from decimal import Decimal

import stripe
from sqlalchemy.orm import Session

from app.domains.billing.providers.base import PaymentProviderAdapter

logger = logging.getLogger(__name__)

# Zero-decimal currencies where 1 unit = 1 whole unit (not cents)
ZERO_DECIMAL_CURRENCIES = {
    "BIF", "CLP", "DJF", "GNF", "JPY", "KMF", "KRW", "MGA",
    "PYG", "RWF", "UGX", "VND", "VUV", "XAF", "XOF", "XPF",
}


def to_minor_units(amount: Decimal, currency: str) -> int:
    """Convert a decimal amount to Stripe minor units.

    Most currencies use cents (multiply by 100).
    Zero-decimal currencies (JPY, KRW, etc.) use whole units.
    """
    if currency.upper() in ZERO_DECIMAL_CURRENCIES:
        return int(amount)
    return int(amount * 100)


class StripeAdapter(PaymentProviderAdapter):
    """Stripe Checkout adapter."""

    def __init__(self, config: dict):
        self.config = config
        self.secret_key = config.get("secret_key", "")
        self.webhook_secret = config.get("webhook_secret", "")

    def _client(self) -> stripe.StripeClient:
        return stripe.StripeClient(self.secret_key)

    def test_connection(self) -> dict:
        """Test Stripe credentials with a real API call."""
        try:
            client = self._client()
            account = client.accounts.retrieve("me")
            return {
                "success": True,
                "message": f"Connected to Stripe account: {account.settings.dashboard.display_name or account.id}",
                "account_id": account.id,
                "country": account.country,
            }
        except stripe.AuthenticationError as exc:
            return {"success": False, "message": f"Authentication failed: {exc}"}
        except Exception as exc:
            return {"success": False, "message": f"Connection failed: {exc}"}

    def create_payment(
        self,
        receipt,
        person,
        currency: str,
        success_url: str,
        cancel_url: str,
        stripe_customer_id: str | None = None,
    ) -> dict:
        """Create a Stripe Checkout Session for a receipt.

        Returns {"redirect_url": str, "session_id": str}.
        """
        client = self._client()

        params = {
            "mode": "payment",
            "line_items": [
                {
                    "price_data": {
                        "currency": currency.lower(),
                        "unit_amount": to_minor_units(receipt.total_amount, currency),
                        "product_data": {
                            "name": receipt.description,
                        },
                    },
                    "quantity": 1,
                }
            ],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": {
                "receipt_id": str(receipt.id),
                "receipt_number": receipt.receipt_number,
            },
        }

        if stripe_customer_id:
            params["customer"] = stripe_customer_id
        else:
            params["customer_email"] = person.email

        session = client.checkout.sessions.create(params=params)

        return {
            "redirect_url": session.url,
            "session_id": session.id,
        }

    def verify_signature(self, headers: dict, raw_body: bytes) -> dict:
        """Verify Stripe webhook signature and return parsed event."""
        sig_header = headers.get("stripe-signature", "")
        if not sig_header:
            raise ValueError("Missing Stripe-Signature header")

        try:
            event = stripe.Webhook.construct_event(
                payload=raw_body,
                sig_header=sig_header,
                secret=self.webhook_secret,
            )
            return event
        except stripe.SignatureVerificationError as exc:
            raise ValueError(f"Invalid signature: {exc}") from exc

    def extract_event_id(self, event_data: dict) -> str:
        return event_data.get("id", "")

    def extract_event_type(self, event_data: dict) -> str:
        return event_data.get("type", "")

    def handle_webhook(self, db: Session, event_data: dict) -> dict:
        """Process Stripe webhook events.

        Handled events:
        - checkout.session.completed → mark receipt paid
        - checkout.session.expired → mark receipt returned
        """
        from app.domains.billing.models import Receipt
        from app.domains.billing.service import validate_status_transition

        event_type = event_data.get("type", "")
        event_obj = event_data.get("data", {}).get("object", {})

        if event_type == "checkout.session.completed":
            return self._handle_checkout_completed(db, event_obj)
        elif event_type == "checkout.session.expired":
            return self._handle_checkout_expired(db, event_obj)
        else:
            return {"ignored": True, "reason": f"Unhandled event type: {event_type}"}

    def _handle_checkout_completed(self, db: Session, session_obj: dict) -> dict:
        """Handle successful Checkout payment."""
        from app.domains.billing.models import Receipt
        from app.domains.billing.service import validate_status_transition

        receipt_id = session_obj.get("metadata", {}).get("receipt_id")
        if not receipt_id:
            return {"ignored": True, "reason": "No receipt_id in metadata"}

        receipt = db.query(Receipt).filter(Receipt.id == int(receipt_id)).first()
        if not receipt:
            return {"ignored": True, "reason": f"Receipt {receipt_id} not found"}

        # Status-guarded transition
        if receipt.status in ("paid", "cancelled"):
            return {
                "ignored": True,
                "reason": f"Receipt already {receipt.status}",
                "receipt_id": receipt.id,
            }

        try:
            validate_status_transition(receipt.status, "paid")
        except Exception:
            return {
                "ignored": True,
                "reason": f"Cannot transition from {receipt.status} to paid",
                "receipt_id": receipt.id,
            }

        receipt.status = "paid"
        receipt.payment_method = "stripe_checkout"
        receipt.payment_date = date.today()
        receipt.stripe_payment_intent_id = session_obj.get("payment_intent")
        receipt.transaction_id = session_obj.get("payment_intent")
        db.flush()

        return {"receipt_id": receipt.id}

    def _handle_checkout_expired(self, db: Session, session_obj: dict) -> dict:
        """Handle expired Checkout session."""
        from app.domains.billing.models import Receipt
        from app.domains.billing.service import validate_status_transition

        receipt_id = session_obj.get("metadata", {}).get("receipt_id")
        if not receipt_id:
            return {"ignored": True, "reason": "No receipt_id in metadata"}

        receipt = db.query(Receipt).filter(Receipt.id == int(receipt_id)).first()
        if not receipt:
            return {"ignored": True, "reason": f"Receipt {receipt_id} not found"}

        # Status-guarded transition
        if receipt.status in ("paid", "cancelled", "returned"):
            return {
                "ignored": True,
                "reason": f"Receipt already {receipt.status}",
                "receipt_id": receipt.id,
            }

        try:
            validate_status_transition(receipt.status, "returned")
        except Exception:
            return {
                "ignored": True,
                "reason": f"Cannot transition from {receipt.status} to returned",
                "receipt_id": receipt.id,
            }

        receipt.status = "returned"
        receipt.return_reason = "Stripe Checkout session expired"
        receipt.return_date = date.today()
        db.flush()

        return {"receipt_id": receipt.id}

    def check_payment_status(self, session_id: str) -> dict:
        """Check status of a Checkout Session."""
        client = self._client()
        session = client.checkout.sessions.retrieve(session_id)
        return {
            "status": session.payment_status,  # paid, unpaid, no_payment_required
            "payment_intent": session.payment_intent,
        }

    def create_invoice(self, receipt, member) -> dict:
        raise NotImplementedError("Stripe Invoice flow deferred to v0.4.5")

    def process_refund(self, payment_id: str, amount: float) -> dict:
        raise NotImplementedError("Refund processing deferred — use Stripe Dashboard")
