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
import secrets
from datetime import date
from decimal import Decimal, InvalidOperation
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

# The order carries the receipt id in its last 8 characters.
MAX_ORDER_RECEIPT_ID = 99_999_999


def build_order_id(receipt_id: int, nonce: int | None = None) -> str:
    """Build a Redsys `Ds_Merchant_Order` for one payment attempt on a receipt.

    Redsys requires exactly 12 chars — first 4 numeric, remaining 8 alphanumeric
    — and rejects an order number it has already seen (`SIS0051 - Pedido
    repetido`). An order derived from the receipt id alone therefore worked
    exactly once per receipt: after a decline, a gateway timeout or a user
    abandoning the TPV page, that receipt could never be paid online again.

    So the first four digits are a per-attempt random nonce and the last eight
    the zero-padded receipt id. Keeping the id in the order means a notification
    for a superseded attempt still resolves to its receipt (see
    ``receipt_id_from_order``) even though the receipt only stores the newest
    order. Two attempts on one receipt drawing the same nonce (1 in 10,000) get
    the same rejection as before; retrying issues a fresh one.

    The old zero-padded format is a special case of this one — nonce 0000 — so
    orders already stored on receipts still parse.
    """
    if receipt_id < 0 or receipt_id > MAX_ORDER_RECEIPT_ID:
        raise ValueError(f"Receipt id out of range for Redsys order: {receipt_id}")
    nonce = secrets.randbelow(10000) if nonce is None else nonce % 10000
    order = f"{nonce:04d}{receipt_id:08d}"
    if not _ORDER_RE.match(order):
        raise ValueError(f"Built order {order!r} does not match Redsys format")
    return order


def receipt_id_from_order(ds_order: str) -> int | None:
    """Recover the receipt id encoded in an order, or None if it is not one of ours."""
    if not ds_order or not _ORDER_RE.match(ds_order):
        return None
    try:
        return int(ds_order[4:])
    except ValueError:
        return None


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


def _amount_mismatch(notified: str | None, expected) -> Decimal | None:
    """The notified amount when it differs from the receipt total, else None.

    python-redsys hands back a Decimal in euros — the same unit ``create_payment``
    passes in — so the two compare directly.

    Returns None when there is nothing to check: no amount on the notification,
    or one that will not parse. A real payment must not be held up by a field we
    failed to read; this check exists to catch a wrong number, not to add a new
    way for a correct payment to be rejected.
    """
    if notified is None:
        return None
    try:
        got = Decimal(str(notified))
    except (InvalidOperation, TypeError, ValueError):
        logger.warning(
            "Could not parse Redsys Ds_Amount %r; amount not checked", notified
        )
        return None
    return got if got != Decimal(str(expected)) else None


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
            # The receipt only stores its newest order, so a notification for an
            # earlier attempt no longer matches on it. The id encoded in the order
            # still resolves it — a late authorisation must not be dropped, or the
            # member is charged with the receipt left unpaid.
            fallback_id = receipt_id_from_order(ds_order)
            if fallback_id is not None:
                receipt = db.query(Receipt).filter(Receipt.id == fallback_id).first()
        if not receipt:
            return {"ignored": True, "reason": f"No receipt for order {ds_order}"}

        mismatch = _amount_mismatch(event_data.get("ds_amount"), receipt.total_amount)
        if mismatch is not None:
            # Authorised, but not for what we asked. Marking it paid in full
            # would write off the difference silently; the signature proves the
            # message is genuine, not that the sum is right. Left unpaid and
            # logged so a person decides — a retry cannot change the amount, so
            # this is reported as handled rather than failed.
            logger.error(
                "Redsys notified %s for receipt %s, which totals %s. Receipt "
                "left unpaid for manual review.",
                mismatch,
                receipt.id,
                receipt.total_amount,
            )
            return {
                "ignored": True,
                "reason": (
                    f"Amount mismatch: notified {mismatch}, "
                    f"expected {receipt.total_amount}"
                ),
                "receipt_id": receipt.id,
            }

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
