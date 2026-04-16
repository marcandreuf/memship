"""Generic webhook receiving endpoint.

Dispatches incoming webhooks to the appropriate payment provider adapter.
No auth — security is via mandatory signature validation per provider.
"""

import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.encryption import decrypt_config
from app.db.session import get_db
from app.domains.billing.models import PaymentProvider
from app.domains.billing.provider_config import get_sensitive_fields
from app.domains.billing import webhook_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Registry of provider types that have real webhook adapters
_ADAPTER_REGISTRY: dict[str, type] = {}

# Auto-register built-in adapters
from app.domains.billing.providers.stripe_provider import StripeAdapter  # noqa: E402

_ADAPTER_REGISTRY["stripe"] = StripeAdapter


def register_adapter(provider_type: str, adapter_class: type) -> None:
    """Register a provider adapter for webhook dispatch."""
    _ADAPTER_REGISTRY[provider_type] = adapter_class


def get_adapter(provider_type: str, config: dict):
    """Instantiate an adapter for the given provider type."""
    adapter_class = _ADAPTER_REGISTRY.get(provider_type)
    if not adapter_class:
        return None
    return adapter_class(config)


@router.post("/{provider_type}")
async def receive_webhook(
    provider_type: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """Receive and process a webhook from a payment provider.

    Flow:
    1. Look up active provider of this type
    2. Verify signature (mandatory — no bypass)
    3. Dedup via external_event_id
    4. Dispatch to adapter.handle_webhook()
    5. Log result
    """
    raw_body = await request.body()

    # 1. Find active provider
    provider = (
        db.query(PaymentProvider)
        .filter(
            PaymentProvider.provider_type == provider_type,
            PaymentProvider.status.in_(["active", "test"]),
        )
        .first()
    )
    if not provider:
        return Response(
            content='{"detail":"No active provider found"}',
            status_code=404,
            media_type="application/json",
        )

    # 2. Get adapter
    adapter = get_adapter(provider_type, _decrypt_provider_config(provider))
    if not adapter:
        return Response(
            content='{"detail":"No webhook adapter registered for this provider"}',
            status_code=404,
            media_type="application/json",
        )

    # 3. Verify signature (mandatory)
    headers = dict(request.headers)
    try:
        event_data = adapter.verify_signature(headers, raw_body)
    except (ValueError, NotImplementedError) as exc:
        logger.warning(
            "Webhook signature validation failed for %s: %s",
            provider_type,
            exc,
        )
        return Response(
            content='{"detail":"Signature validation failed"}',
            status_code=400,
            media_type="application/json",
        )

    # 4. Extract event identity
    external_event_id = adapter.extract_event_id(event_data)
    event_type = adapter.extract_event_type(event_data)

    # 5. Dedup — log event, returns None if duplicate
    event = webhook_service.log_event(
        db, provider_type, external_event_id, event_type, event_data
    )
    if event is None:
        return Response(
            content='{"detail":"Duplicate event"}',
            status_code=200,
            media_type="application/json",
        )

    # 6. Dispatch to adapter handler inside a savepoint
    #    so a failure doesn't lose the event row
    savepoint = db.begin_nested()
    try:
        result = adapter.handle_webhook(db, event_data)
        receipt_id = result.get("receipt_id") if result else None
        if result and result.get("ignored"):
            webhook_service.mark_ignored(
                db, event, result.get("reason", "Ignored by handler")
            )
        else:
            webhook_service.mark_processed(db, event, receipt_id)
        savepoint.commit()
        db.commit()
    except Exception as exc:
        savepoint.rollback()
        webhook_service.mark_failed(db, event, str(exc))
        db.commit()

        logger.exception(
            "Webhook handler failed for %s event %s",
            provider_type,
            external_event_id,
        )
        return Response(
            content='{"detail":"Webhook processing failed"}',
            status_code=500,
            media_type="application/json",
        )

    return Response(
        content='{"detail":"OK"}',
        status_code=200,
        media_type="application/json",
    )


def _decrypt_provider_config(provider: PaymentProvider) -> dict:
    """Decrypt a provider's config for adapter use."""
    sensitive = get_sensitive_fields(provider.provider_type)
    return decrypt_config(provider.config or {}, sensitive)
