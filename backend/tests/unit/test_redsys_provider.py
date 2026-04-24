"""Unit tests for Redsys provider adapter — no external I/O.

Signature crypto is delegated to python-redsys; a known-answer test pins the
wiring so an accidental library swap won't break silently in production.
"""

from decimal import ROUND_HALF_UP, Decimal
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
from redsys.client import RedirectClient
from redsys.request import Request as _RedsysRequest
from redsys.response import Response as _RedsysResponse

from app.domains.billing.providers.redsys_provider import (
    METHOD_BIZUM,
    RedsysAdapter,
    build_order_id,
    map_response_to_outcome,
)


@pytest.fixture(autouse=True)
def _reset_redsys_library_state():
    """python-redsys 1.2 stores ``_parameters`` on the class, leaking state
    between tests. Reset to a fresh dict before and after each test."""
    _RedsysRequest._parameters = {}
    _RedsysResponse._parameters = {}
    yield
    _RedsysRequest._parameters = {}
    _RedsysResponse._parameters = {}


def _sign_notification(
    secret_key: str,
    *,
    ds_order: str,
    ds_response: str = "0000",
    ds_auth_code: str = "123456",
    ds_amount: int = 5000,
    ds_currency: int = 978,
) -> dict:
    """Build a Response-shape signed notification envelope, as Redsys sends it."""
    client = RedirectClient(secret_key)
    merchant_parameters = {
        "Ds_MerchantCode": "100000001",
        "Ds_Terminal": "1",
        "Ds_TransactionType": "0",
        "Ds_Currency": ds_currency,
        "Ds_Order": ds_order,
        "Ds_Amount": ds_amount,
        "Ds_Response": ds_response,
        "Ds_AuthorisationCode": ds_auth_code,
        "Ds_Date": "23%2F04%2F2026",
        "Ds_Hour": "10%3A00",
    }
    encoded = client.encode_parameters(merchant_parameters)
    signature = client.generate_signature(ds_order, encoded)
    return {
        "Ds_SignatureVersion": "HMAC_SHA256_V1",
        "Ds_MerchantParameters": encoded.decode(),
        "Ds_Signature": signature.decode(),
    }


# --- helpers ---

VALID_CONFIG = {
    "merchant_code": "100000001",
    "terminal_id": "1",
    "secret_key": "sq7HjrUOBfKmC576ILgskD5srU870gJ7",
    "environment": "test",
    "currency_code": "978",
}


def fake_receipt(receipt_id: int = 42, amount: str = "50.00", description: str = "Membership"):
    return SimpleNamespace(
        id=receipt_id,
        total_amount=Decimal(amount),
        description=description,
        status="emitted",
        payment_method=None,
    )


def fake_person(email: str = "m@test.com"):
    return SimpleNamespace(email=email)


# --- build_order_id ---


class TestBuildOrderId:
    def test_small_id_zero_padded_to_12(self):
        assert build_order_id(1) == "000000000001"

    def test_larger_id(self):
        assert build_order_id(123456) == "000000123456"

    def test_max_12_digit_id(self):
        assert build_order_id(999999999999) == "999999999999"

    def test_overflow_raises(self):
        with pytest.raises(ValueError, match="too large"):
            build_order_id(1_000_000_000_000)


# --- map_response_to_outcome ---


class TestResponseCodeMapping:
    @pytest.mark.parametrize("code", ["0000", "0001", "0050", "0099"])
    def test_authorized_codes_map_to_paid(self, code):
        assert map_response_to_outcome(code) == "paid"

    @pytest.mark.parametrize("code", ["0100", "0180", "9915", "0900", "0913"])
    def test_non_authorized_codes_map_to_denied(self, code):
        assert map_response_to_outcome(code) == "denied"

    def test_non_numeric_maps_to_denied(self):
        assert map_response_to_outcome("ABCD") == "denied"

    def test_empty_maps_to_denied(self):
        assert map_response_to_outcome("") == "denied"


# --- test_connection ---


class TestTestConnection:
    def test_valid_config_passes(self):
        adapter = RedsysAdapter(VALID_CONFIG)
        result = adapter.test_connection()
        assert result["success"] is True
        assert "test" in result["message"]

    def test_missing_merchant_code(self):
        config = {**VALID_CONFIG, "merchant_code": ""}
        result = RedsysAdapter(config).test_connection()
        assert result["success"] is False

    def test_non_numeric_merchant_code(self):
        config = {**VALID_CONFIG, "merchant_code": "ABCDE1234"}
        result = RedsysAdapter(config).test_connection()
        assert result["success"] is False

    def test_non_numeric_terminal_id(self):
        config = {**VALID_CONFIG, "terminal_id": "abc"}
        result = RedsysAdapter(config).test_connection()
        assert result["success"] is False

    def test_non_numeric_currency(self):
        config = {**VALID_CONFIG, "currency_code": "EUR"}
        result = RedsysAdapter(config).test_connection()
        assert result["success"] is False

    def test_production_env_tpv_url(self):
        config = {**VALID_CONFIG, "environment": "production"}
        adapter = RedsysAdapter(config)
        assert "sis.redsys.es" in adapter.tpv_url
        assert "sis-t" not in adapter.tpv_url

    def test_test_env_tpv_url(self):
        adapter = RedsysAdapter(VALID_CONFIG)
        assert "sis-t.redsys.es" in adapter.tpv_url


# --- create_payment ---


class TestCreatePayment:
    def test_returns_redirect_url_and_form_params(self):
        adapter = RedsysAdapter(VALID_CONFIG)
        result = adapter.create_payment(
            receipt=fake_receipt(),
            person=fake_person(),
            success_url="https://example.test/ok",
            cancel_url="https://example.test/ko",
            merchant_url="https://example.test/api/v1/webhooks/redsys",
        )
        assert result["redirect_url"].startswith("https://sis-t.redsys.es")
        assert result["ds_order"] == "000000000042"
        assert set(result["form_params"].keys()) == {
            "Ds_SignatureVersion",
            "Ds_MerchantParameters",
            "Ds_Signature",
        }
        assert result["form_params"]["Ds_SignatureVersion"] == "HMAC_SHA256_V1"
        assert result["form_params"]["Ds_MerchantParameters"]
        assert result["form_params"]["Ds_Signature"]

    def test_bizum_method_included_in_params(self):
        adapter = RedsysAdapter(VALID_CONFIG)
        result = adapter.create_payment(
            receipt=fake_receipt(),
            person=fake_person(),
            success_url="https://example.test/ok",
            cancel_url="https://example.test/ko",
            merchant_url="https://example.test/webhook",
            method="bizum",
        )
        decoded = RedirectClient(VALID_CONFIG["secret_key"]).decode_parameters(
            result["form_params"]["Ds_MerchantParameters"].encode()
        )
        assert decoded.get("Ds_Merchant_PayMethods") == METHOD_BIZUM


# --- verify_signature roundtrip + known-answer ---


class TestVerifyNotificationSignature:
    """Redsys's async notification envelope uses Response-shape keys
    (`Ds_Order`, `Ds_Response`, …) — distinct from the request envelope
    produced by `create_payment` (which uses `Ds_Merchant_*`)."""

    def test_valid_notification_accepted(self):
        adapter = RedsysAdapter(VALID_CONFIG)
        form = _sign_notification(
            VALID_CONFIG["secret_key"], ds_order="000000000007"
        )
        raw_body = urlencode(form).encode()
        verified = adapter.verify_signature(headers={}, raw_body=raw_body)
        assert verified["ds_order"] == "000000000007"
        assert verified["ds_response"] == "0000"
        assert verified["ds_auth_code"] == "123456"

    def test_tampered_parameters_rejected(self):
        adapter = RedsysAdapter(VALID_CONFIG)
        form = _sign_notification(
            VALID_CONFIG["secret_key"], ds_order="000000000007"
        )
        form["Ds_MerchantParameters"] = "A" + form["Ds_MerchantParameters"][1:]
        raw_body = urlencode(form).encode()
        with pytest.raises(ValueError, match="Invalid Redsys signature"):
            adapter.verify_signature(headers={}, raw_body=raw_body)

    def test_missing_signature_rejected(self):
        adapter = RedsysAdapter(VALID_CONFIG)
        raw_body = urlencode({"Ds_SignatureVersion": "HMAC_SHA256_V1"}).encode()
        with pytest.raises(ValueError, match="Missing"):
            adapter.verify_signature(headers={}, raw_body=raw_body)

    def test_wrong_secret_rejects_signature(self):
        form = _sign_notification(
            VALID_CONFIG["secret_key"], ds_order="000000000007"
        )
        wrong = RedsysAdapter({**VALID_CONFIG, "secret_key": "X" * 32})
        raw_body = urlencode(form).encode()
        with pytest.raises(ValueError, match="Invalid Redsys signature"):
            wrong.verify_signature(headers={}, raw_body=raw_body)


class TestKnownAnswer:
    """Pin crypto wiring against the python-redsys public test vector.

    If this breaks, the dependency behaviour changed — inspect before patching.
    """

    def test_hmac_sha256_matches_library_vector(self):
        client = RedirectClient("sq7HjrUOBfKmC576ILgskD5srU870gJ7")
        params = {
            "merchant_code": "100000001",
            "terminal": "1",
            "transaction_type": "0",
            "currency": 978,
            "order": "000000000001",
            "amount": Decimal("10.56489").quantize(Decimal(".01"), ROUND_HALF_UP),
            "merchant_data": "test merchant data",
            "merchant_name": "Example Commerce",
            "titular": "Example Ltd.",
            "product_description": "Products of Example Commerce",
            "merchant_url": "https://example.com/redsys/response",
        }
        prepared = client.prepare_request(params)
        assert (
            prepared["Ds_Signature"]
            == b"a2F05DwuH5aXu5vD1IdjQ+NxaR0lPsRwksW1nr2Nzuw="
        )


# --- extract_event_id / extract_event_type ---


class TestEventExtraction:
    def test_event_id_is_deterministic(self):
        adapter = RedsysAdapter(VALID_CONFIG)
        event = {
            "ds_response": "0000",
            "raw_parameters": {
                "Ds_Order": "000000000042",
                "Ds_Date": "23%2F04%2F2026",
                "Ds_Hour": "10%3A00",
                "Ds_Response": "0000",
            },
        }
        assert adapter.extract_event_id(event) == adapter.extract_event_id(event)
        assert "000000000042" in adapter.extract_event_id(event)

    def test_event_type_paid(self):
        adapter = RedsysAdapter(VALID_CONFIG)
        assert adapter.extract_event_type({"ds_response": "0000"}) == "payment.paid"

    def test_event_type_denied(self):
        adapter = RedsysAdapter(VALID_CONFIG)
        assert adapter.extract_event_type({"ds_response": "0180"}) == "payment.denied"
