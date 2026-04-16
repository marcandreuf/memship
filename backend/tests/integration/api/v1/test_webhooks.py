"""Integration tests for the generic webhook endpoint."""

import json

from app.core.encryption import encrypt_config
from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.billing.models import PaymentProvider, WebhookEvent
from app.domains.billing.providers.base import PaymentProviderAdapter
from app.domains.persons.models import Person
from app.api.v1.endpoints.webhooks import register_adapter, _ADAPTER_REGISTRY


# --- Mock adapter for testing ---


class MockAdapter(PaymentProviderAdapter):
    """Test adapter that verifies a simple signature and handles events."""

    VALID_SIGNATURE = "test-valid-signature"

    def __init__(self, config: dict):
        self.config = config

    def test_connection(self) -> dict:
        return {"success": True, "message": "Mock OK"}

    def extract_event_id(self, event_data: dict) -> str:
        return event_data.get("id", "unknown")

    def extract_event_type(self, event_data: dict) -> str:
        return event_data.get("type", "unknown")

    def verify_signature(self, headers: dict, raw_body: bytes) -> dict:
        sig = headers.get("x-test-signature", "")
        if sig != self.VALID_SIGNATURE:
            raise ValueError("Invalid test signature")
        return json.loads(raw_body)

    def create_payment(self, receipt, member) -> dict:
        raise NotImplementedError

    def check_payment_status(self, payment_id: str) -> str:
        raise NotImplementedError

    def handle_webhook(self, db, event_data: dict) -> dict:
        event_type = event_data.get("type")
        if event_type == "test.ignored":
            return {"ignored": True, "reason": "Test ignored event"}
        if event_type == "test.error":
            raise RuntimeError("Test handler error")
        return {"receipt_id": event_data.get("receipt_id")}

    def process_refund(self, payment_id: str, amount: float) -> dict:
        raise NotImplementedError


# --- Helpers ---


def _setup_mock_adapter():
    """Register mock adapter for 'mock_provider' type."""
    register_adapter("mock_provider", MockAdapter)


def _teardown_mock_adapter():
    """Remove mock adapter registration."""
    _ADAPTER_REGISTRY.pop("mock_provider", None)


def _create_provider(db, provider_type="mock_provider", status="active"):
    provider = PaymentProvider(
        provider_type=provider_type,
        display_name="Mock Provider",
        status=status,
        config={},
        is_default=False,
    )
    db.add(provider)
    db.flush()
    return provider


def _webhook_payload(event_id="evt_001", event_type="test.success", receipt_id=None):
    data = {"id": event_id, "type": event_type}
    if receipt_id:
        data["receipt_id"] = receipt_id
    return data


# --- Tests ---


class TestWebhookUnknownProvider:
    def test_unknown_provider_returns_404(self, client, db):
        resp = client.post(
            "/api/v1/webhooks/nonexistent",
            content=b"{}",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 404

    def test_disabled_provider_returns_404(self, client, db):
        _setup_mock_adapter()
        try:
            _create_provider(db, status="disabled")
            resp = client.post(
                "/api/v1/webhooks/mock_provider",
                content=b"{}",
                headers={"content-type": "application/json"},
            )
            assert resp.status_code == 404
        finally:
            _teardown_mock_adapter()

    def test_no_registered_adapter_returns_404(self, client, db):
        # Provider exists in DB but no adapter registered
        _create_provider(db, provider_type="unregistered_type")
        resp = client.post(
            "/api/v1/webhooks/unregistered_type",
            content=b"{}",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 404


class TestWebhookSignatureValidation:
    def test_missing_signature_returns_400(self, client, db):
        _setup_mock_adapter()
        try:
            _create_provider(db)
            payload = _webhook_payload()
            resp = client.post(
                "/api/v1/webhooks/mock_provider",
                content=json.dumps(payload).encode(),
                headers={"content-type": "application/json"},
            )
            assert resp.status_code == 400
            assert "Signature validation failed" in resp.json()["detail"]
        finally:
            _teardown_mock_adapter()

    def test_invalid_signature_returns_400(self, client, db):
        _setup_mock_adapter()
        try:
            _create_provider(db)
            payload = _webhook_payload()
            resp = client.post(
                "/api/v1/webhooks/mock_provider",
                content=json.dumps(payload).encode(),
                headers={
                    "content-type": "application/json",
                    "x-test-signature": "wrong-signature",
                },
            )
            assert resp.status_code == 400
        finally:
            _teardown_mock_adapter()

    def test_valid_signature_accepted(self, client, db):
        _setup_mock_adapter()
        try:
            _create_provider(db)
            payload = _webhook_payload()
            resp = client.post(
                "/api/v1/webhooks/mock_provider",
                content=json.dumps(payload).encode(),
                headers={
                    "content-type": "application/json",
                    "x-test-signature": MockAdapter.VALID_SIGNATURE,
                },
            )
            assert resp.status_code == 200
        finally:
            _teardown_mock_adapter()


class TestWebhookIdempotency:
    def test_duplicate_event_returns_200_no_reprocess(self, client, db):
        _setup_mock_adapter()
        try:
            _create_provider(db)
            payload = _webhook_payload(event_id="evt_dup_001")
            headers = {
                "content-type": "application/json",
                "x-test-signature": MockAdapter.VALID_SIGNATURE,
            }

            # First call
            resp1 = client.post(
                "/api/v1/webhooks/mock_provider",
                content=json.dumps(payload).encode(),
                headers=headers,
            )
            assert resp1.status_code == 200
            assert resp1.json()["detail"] == "OK"

            # Second call — same event ID
            resp2 = client.post(
                "/api/v1/webhooks/mock_provider",
                content=json.dumps(payload).encode(),
                headers=headers,
            )
            assert resp2.status_code == 200
            assert resp2.json()["detail"] == "Duplicate event"

            # Verify only one event row
            count = (
                db.query(WebhookEvent)
                .filter(WebhookEvent.external_event_id == "evt_dup_001")
                .count()
            )
            assert count == 1
        finally:
            _teardown_mock_adapter()

    def test_different_events_both_processed(self, client, db):
        _setup_mock_adapter()
        try:
            _create_provider(db)
            headers = {
                "content-type": "application/json",
                "x-test-signature": MockAdapter.VALID_SIGNATURE,
            }

            resp1 = client.post(
                "/api/v1/webhooks/mock_provider",
                content=json.dumps(_webhook_payload(event_id="evt_a")).encode(),
                headers=headers,
            )
            resp2 = client.post(
                "/api/v1/webhooks/mock_provider",
                content=json.dumps(_webhook_payload(event_id="evt_b")).encode(),
                headers=headers,
            )
            assert resp1.status_code == 200
            assert resp2.status_code == 200

            count = (
                db.query(WebhookEvent)
                .filter(WebhookEvent.provider_type == "mock_provider")
                .count()
            )
            assert count == 2
        finally:
            _teardown_mock_adapter()


class TestWebhookProcessing:
    def test_successful_event_marked_processed(self, client, db):
        _setup_mock_adapter()
        try:
            _create_provider(db)
            payload = _webhook_payload(event_id="evt_proc_001")
            resp = client.post(
                "/api/v1/webhooks/mock_provider",
                content=json.dumps(payload).encode(),
                headers={
                    "content-type": "application/json",
                    "x-test-signature": MockAdapter.VALID_SIGNATURE,
                },
            )
            assert resp.status_code == 200

            event = (
                db.query(WebhookEvent)
                .filter(WebhookEvent.external_event_id == "evt_proc_001")
                .first()
            )
            assert event is not None
            assert event.status == "processed"
            assert event.event_type == "test.success"
            assert event.processed_at is not None
        finally:
            _teardown_mock_adapter()

    def test_ignored_event_marked_ignored(self, client, db):
        _setup_mock_adapter()
        try:
            _create_provider(db)
            payload = _webhook_payload(
                event_id="evt_ign_001", event_type="test.ignored"
            )
            resp = client.post(
                "/api/v1/webhooks/mock_provider",
                content=json.dumps(payload).encode(),
                headers={
                    "content-type": "application/json",
                    "x-test-signature": MockAdapter.VALID_SIGNATURE,
                },
            )
            assert resp.status_code == 200

            event = (
                db.query(WebhookEvent)
                .filter(WebhookEvent.external_event_id == "evt_ign_001")
                .first()
            )
            assert event is not None
            assert event.status == "ignored"
            assert event.error_message == "Test ignored event"
        finally:
            _teardown_mock_adapter()

    def test_handler_error_returns_500_marks_failed(self, client, db):
        _setup_mock_adapter()
        try:
            _create_provider(db)
            payload = _webhook_payload(
                event_id="evt_err_001", event_type="test.error"
            )
            resp = client.post(
                "/api/v1/webhooks/mock_provider",
                content=json.dumps(payload).encode(),
                headers={
                    "content-type": "application/json",
                    "x-test-signature": MockAdapter.VALID_SIGNATURE,
                },
            )
            assert resp.status_code == 500

            event = (
                db.query(WebhookEvent)
                .filter(WebhookEvent.external_event_id == "evt_err_001")
                .first()
            )
            assert event is not None
            assert event.status == "failed"
            assert "Test handler error" in event.error_message
        finally:
            _teardown_mock_adapter()

    def test_event_payload_stored(self, client, db):
        _setup_mock_adapter()
        try:
            _create_provider(db)
            payload = _webhook_payload(event_id="evt_payload_001")
            resp = client.post(
                "/api/v1/webhooks/mock_provider",
                content=json.dumps(payload).encode(),
                headers={
                    "content-type": "application/json",
                    "x-test-signature": MockAdapter.VALID_SIGNATURE,
                },
            )
            assert resp.status_code == 200

            event = (
                db.query(WebhookEvent)
                .filter(WebhookEvent.external_event_id == "evt_payload_001")
                .first()
            )
            assert event.payload == payload
            assert event.provider_type == "mock_provider"
        finally:
            _teardown_mock_adapter()

    def test_test_status_provider_accepts_webhooks(self, client, db):
        _setup_mock_adapter()
        try:
            _create_provider(db, status="test")
            payload = _webhook_payload(event_id="evt_test_status_001")
            resp = client.post(
                "/api/v1/webhooks/mock_provider",
                content=json.dumps(payload).encode(),
                headers={
                    "content-type": "application/json",
                    "x-test-signature": MockAdapter.VALID_SIGNATURE,
                },
            )
            assert resp.status_code == 200
        finally:
            _teardown_mock_adapter()
