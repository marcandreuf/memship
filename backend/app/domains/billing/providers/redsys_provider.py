"""Redsys payment provider adapter — redirect + async notification.

Implements PaymentProviderAdapter for Redsys SIS (TPV Virtual).

Flow:
1. `create_payment()` builds HMAC-SHA256 signed form params; the frontend
   auto-submits an HTML form to the TPV URL.
2. User completes payment on the Redsys hosted page; browser redirects to
   URL_OK or URL_KO (user-facing only — not authoritative).
3. Redsys also posts an async notification to `MERCHANT_URL`
   (`/api/v1/webhooks/redsys`). `handle_webhook()` validates the signature,
   maps `Ds_Response`, and updates the receipt. This is the source of truth.

Crypto (3DES key derivation + HMAC-SHA256) is delegated to `python-redsys`.
"""

import logging
import re
from datetime import date
from decimal import Decimal
from urllib.parse import parse_qs

from redsys.client import RedirectClient
from sqlalchemy.orm import Session

from app.domains.billing.providers.base import PaymentProviderAdapter

logger = logging.getLogger(__name__)

REDSYS_URLS = {
    "test": "https://sis-t.redsys.es:25443/sis/realizarPago",
    "production": "https://sis.redsys.es/sis/realizarPago",
}

TX_STANDARD_PAYMENT = "0"
METHOD_BIZUM = "z"

LANGUAGE_MAP = {"es": "001", "en": "002", "ca": "003"}

_ORDER_RE = re.compile(r"^[0-9]{4}[a-zA-Z0-9]{8}$")


def build_order_id(receipt_id: int) -> str:
    """Build a Redsys `Ds_Merchant_Order` from a receipt id.

    Redsys requires exactly 12 chars: first 4 numeric, remaining 8
    alphanumeric. Zero-padded decimal receipt id satisfies both.
    """
    s = str(receipt_id)
    if len(s) > 12:
        raise ValueError(f"Receipt id too large for Redsys order: {receipt_id}")
    order = s.zfill(12)
    if not _ORDER_RE.match(order):
        raise ValueError(f"Built order {order!r} does not match Redsys format")
    return order


def map_response_to_outcome(ds_response: str) -> str:
    """Map `Ds_Response` code to outcome.

    0000-0099: authorized (`paid`)
    900      : refund authorized (not used in v0.4.3)
    others   : denied
    """
    try:
        code = int(ds_response)
    except (ValueError, TypeError):
        return "denied"
    if 0 <= code <= 99:
        return "paid"
    return "denied"


class RedsysAdapter(PaymentProviderAdapter):
    """Redsys SIS (TPV Virtual) adapter."""

    def __init__(self, config: dict):
        self.config = config
        self.merchant_code = config.get("merchant_code", "")
        self.terminal_id = config.get("terminal_id", "")
        self.secret_key = config.get("secret_key", "")
        self.environment = config.get("environment", "test")
        self.currency_code = config.get("currency_code", "978")

    @property
    def tpv_url(self) -> str:
        return REDSYS_URLS.get(self.environment, REDSYS_URLS["test"])

    def _client(self) -> RedirectClient:
        return RedirectClient(self.secret_key)

    def test_connection(self) -> dict:
        """Local config validation — Redsys has no ping endpoint."""
        from app.domains.billing.provider_config import validate_provider_config

        errors = validate_provider_config("redsys", self.config)
        if errors:
            return {"success": False, "message": "; ".join(errors)}
        if not self.merchant_code.isdigit() or not (7 <= len(self.merchant_code) <= 9):
            return {"success": False, "message": "Merchant Code must be 7-9 digits"}
        if not self.terminal_id.isdigit():
            return {"success": False, "message": "Terminal ID must be numeric"}
        try:
            int(self.currency_code)
        except (ValueError, TypeError):
            return {"success": False, "message": "Currency Code must be ISO 4217 numeric"}
        return {
            "success": True,
            "message": f"Redsys config valid ({self.environment})",
        }

    def create_payment(
        self,
        receipt,
        person,
        success_url: str,
        cancel_url: str,
        merchant_url: str,
        method: str = "card",
        locale: str = "es",
    ) -> dict:
        """Build signed form params for redirect to the Redsys TPV.

        Returns
        -------
        {
            "redirect_url": str,   # TPV endpoint to POST the form to
            "form_params": dict,   # Ds_SignatureVersion / Ds_MerchantParameters / Ds_Signature
            "ds_order": str,       # caller should persist on the receipt
        }
        """
        client = self._client()
        order = build_order_id(receipt.id)
        amount = Decimal(receipt.total_amount)

        params = {
            "merchant_code": self.merchant_code,
            "terminal": self.terminal_id,
            "transaction_type": TX_STANDARD_PAYMENT,
            "order": order,
            "currency": int(self.currency_code),
            "amount": amount,
            "product_description": (receipt.description or "")[:125],
            "url_ok": success_url,
            "url_ko": cancel_url,
            "merchant_url": merchant_url,
            "consumer_language": LANGUAGE_MAP.get(locale, "001"),
        }
        if method == "bizum":
            params["payment_method"] = METHOD_BIZUM

        form_params = client.prepare_request(params)
        return {
            "redirect_url": self.tpv_url,
            "form_params": {
                "Ds_SignatureVersion": form_params["Ds_SignatureVersion"],
                "Ds_MerchantParameters": form_params["Ds_MerchantParameters"].decode(),
                "Ds_Signature": form_params["Ds_Signature"].decode(),
            },
            "ds_order": order,
        }

    def verify_signature(self, headers: dict, raw_body: bytes) -> dict:
        """Verify a Redsys async notification signature.

        Redsys posts `application/x-www-form-urlencoded` with
        `Ds_SignatureVersion`, `Ds_MerchantParameters`, `Ds_Signature`.
        """
        form = {k: v[0] for k, v in parse_qs(raw_body.decode()).items()}
        merchant_parameters = form.get("Ds_MerchantParameters", "")
        signature = form.get("Ds_Signature", "")
        if not merchant_parameters or not signature:
            raise ValueError("Missing Ds_MerchantParameters or Ds_Signature")

        client = self._client()
        try:
            response = client.create_response(signature, merchant_parameters)
        except ValueError as exc:
            raise ValueError(f"Invalid Redsys signature: {exc}") from exc

        raw = client.decode_parameters(merchant_parameters.encode())
        return {
            "ds_order": response.order,
            "ds_response": response.response,
            "ds_auth_code": response.authorization_code,
            "ds_amount": str(response.amount) if response.amount is not None else None,
            "raw_parameters": raw,
        }

    def extract_event_id(self, event_data: dict) -> str:
        """Synthesize an event id from order + date + hour (Redsys has no native id)."""
        raw = event_data.get("raw_parameters", {})
        return (
            f"redsys-{raw.get('Ds_Order', '')}-"
            f"{raw.get('Ds_Date', '')}{raw.get('Ds_Hour', '')}-"
            f"{raw.get('Ds_Response', '')}"
        )

    def extract_event_type(self, event_data: dict) -> str:
        return f"payment.{map_response_to_outcome(event_data.get('ds_response', ''))}"

    def handle_webhook(self, db: Session, event_data: dict) -> dict:
        """Apply a verified Redsys notification to the matching receipt."""
        from app.domains.billing.models import Receipt
        from app.domains.billing.service import validate_status_transition

        ds_order = event_data.get("ds_order")
        ds_response = event_data.get("ds_response", "")
        ds_auth_code = event_data.get("ds_auth_code", "") or ""

        if not ds_order:
            return {"ignored": True, "reason": "Missing Ds_Order"}

        receipt = (
            db.query(Receipt).filter(Receipt.redsys_ds_order == ds_order).first()
        )
        if not receipt:
            return {"ignored": True, "reason": f"No receipt for order {ds_order}"}

        outcome = map_response_to_outcome(ds_response)
        if outcome != "paid":
            return {
                "ignored": True,
                "reason": f"Payment denied (Ds_Response={ds_response})",
                "receipt_id": receipt.id,
                "outcome": "denied",
            }

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
        # Preserve 'bizum' if create_payment set it; otherwise default to 'redsys'
        if receipt.payment_method not in ("redsys", "bizum"):
            receipt.payment_method = "redsys"
        receipt.payment_date = date.today()
        receipt.redsys_auth_code = ds_auth_code[:8]
        receipt.transaction_id = ds_auth_code or None
        db.flush()

        return {"receipt_id": receipt.id, "outcome": "paid"}

    def check_payment_status(self, payment_id: str) -> dict:
        raise NotImplementedError("Redsys REST query API not in scope for v0.4.3")

    def process_refund(self, payment_id: str, amount: float) -> dict:
        raise NotImplementedError(
            "Redsys refunds not in scope for v0.4.3 — use bank portal"
        )
