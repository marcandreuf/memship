"""Abstract payment provider adapter interface.

All payment providers implement this interface. In v0.4.1, only
test_connection() is implemented (as local config validation).
Real payment processing methods are implemented per provider
starting from v0.4.2.
"""

from abc import ABC, abstractmethod


class PaymentProviderAdapter(ABC):
    """Base class for all payment provider adapters."""

    @abstractmethod
    def test_connection(self) -> dict:
        """Test provider credentials.

        In v0.4.1, this performs local config validation only
        (required fields, format checks). Real API pings are
        added when each provider is implemented (v0.4.2+).

        Returns:
            {"success": bool, "message": str}
        """

    @abstractmethod
    def create_payment(self, receipt, member) -> dict:
        """Create a payment.

        Returns:
            {"redirect_url": str} for redirect-based providers, or
            {"payment_id": str} for API-based providers.
        """

    @abstractmethod
    def check_payment_status(self, payment_id: str) -> str:
        """Check payment status.

        Returns:
            Status string (e.g. "paid", "pending", "failed").
        """

    @abstractmethod
    def extract_event_id(self, event_data: dict) -> str:
        """Extract the unique event ID from a verified webhook payload."""

    @abstractmethod
    def extract_event_type(self, event_data: dict) -> str:
        """Extract the event type string from a verified webhook payload."""

    @abstractmethod
    def verify_signature(self, headers: dict, raw_body: bytes) -> dict:
        """Verify webhook signature.

        Args:
            headers: Request headers (provider-specific signature header).
            raw_body: Raw request body bytes (needed for HMAC verification).

        Returns:
            Parsed and verified event payload dict.

        Raises:
            ValueError: If signature is invalid or missing.
        """

    @abstractmethod
    def handle_webhook(self, request_data: dict) -> dict:
        """Process webhook event.

        Returns:
            Parsed event data.
        """

    @abstractmethod
    def process_refund(self, payment_id: str, amount: float) -> dict:
        """Process a refund.

        Returns:
            Refund result dict.
        """


class LocalValidationAdapter(PaymentProviderAdapter):
    """Adapter that only performs local config validation.

    Used in v0.4.1 for all provider types. Validates required fields
    and format rules without making external API calls.
    """

    def __init__(self, provider_type: str, config: dict):
        self.provider_type = provider_type
        self.config = config

    def test_connection(self) -> dict:
        from app.domains.billing.provider_config import validate_provider_config

        errors = validate_provider_config(self.provider_type, self.config)
        if errors:
            return {"success": False, "message": "; ".join(errors)}
        return {"success": True, "message": "Configuration is valid"}

    def create_payment(self, receipt, member) -> dict:
        raise NotImplementedError(
            f"Payment processing for '{self.provider_type}' is not yet implemented"
        )

    def check_payment_status(self, payment_id: str) -> str:
        raise NotImplementedError(
            f"Payment status check for '{self.provider_type}' is not yet implemented"
        )

    def extract_event_id(self, event_data: dict) -> str:
        raise NotImplementedError(
            f"Event ID extraction for '{self.provider_type}' is not yet implemented"
        )

    def extract_event_type(self, event_data: dict) -> str:
        raise NotImplementedError(
            f"Event type extraction for '{self.provider_type}' is not yet implemented"
        )

    def verify_signature(self, headers: dict, raw_body: bytes) -> dict:
        raise NotImplementedError(
            f"Webhook signature verification for '{self.provider_type}' is not yet implemented"
        )

    def handle_webhook(self, request_data: dict) -> dict:
        raise NotImplementedError(
            f"Webhook handling for '{self.provider_type}' is not yet implemented"
        )

    def process_refund(self, payment_id: str, amount: float) -> dict:
        raise NotImplementedError(
            f"Refund processing for '{self.provider_type}' is not yet implemented"
        )
