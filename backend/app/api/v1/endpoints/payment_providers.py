"""Payment provider management endpoints (super_admin only)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.authorization import require_super_admin
from app.core.encryption import decrypt_config, encrypt_config, mask_config
from app.core.pagination import paginate
from app.db.session import get_db
from app.domains.auth.models import User
from app.domains.billing.models import PaymentProvider, Receipt
from app.domains.billing.provider_config import (
    PROVIDER_CONFIG_SCHEMAS,
    get_sensitive_fields,
)
from app.domains.billing.providers.base import LocalValidationAdapter
from app.domains.billing.schemas import (
    PaymentProviderCreate,
    PaymentProviderResponse,
    PaymentProviderUpdate,
)

router = APIRouter(prefix="/payment-providers", tags=["payment-providers"])


def _mask_provider(provider: PaymentProvider) -> dict:
    """Convert a provider model to a response dict with masked config."""
    sensitive = get_sensitive_fields(provider.provider_type)
    decrypted = decrypt_config(provider.config or {}, sensitive)
    masked = mask_config(decrypted, sensitive)
    data = PaymentProviderResponse.model_validate(provider).model_dump()
    data["config"] = masked
    return data


@router.get("/types")
def list_provider_types(
    current_user: User = Depends(require_super_admin),
):
    """List available provider types with config schemas and availability status."""
    # Providers with real payment processing implemented
    available_types = {"sepa_direct_debit"}

    result = []
    for provider_type, schema in PROVIDER_CONFIG_SCHEMAS.items():
        result.append({
            "provider_type": provider_type,
            "fields": schema["fields"],
            "sensitive_fields": schema["sensitive_fields"],
            "available": provider_type in available_types,
        })
    return result


@router.get("/", response_model=dict)
def list_providers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """List all configured payment providers (config masked)."""
    query = db.query(PaymentProvider).order_by(PaymentProvider.id)
    items, meta = paginate(query, page, page_size)

    return {
        "items": [_mask_provider(p) for p in items],
        "meta": meta.model_dump(),
    }


@router.get("/{provider_id}", response_model=dict)
def get_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Get provider detail (config masked)."""
    provider = db.query(PaymentProvider).filter(
        PaymentProvider.id == provider_id
    ).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Payment provider not found")

    return _mask_provider(provider)


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=dict)
def create_provider(
    data: PaymentProviderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Create a new payment provider. One provider per type enforced."""
    # Check one-per-type constraint
    existing = db.query(PaymentProvider).filter(
        PaymentProvider.provider_type == data.provider_type
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A provider of type '{data.provider_type}' already exists",
        )

    # Validate provider type is known
    if data.provider_type not in PROVIDER_CONFIG_SCHEMAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown provider type: {data.provider_type}",
        )

    # Encrypt sensitive fields
    sensitive = get_sensitive_fields(data.provider_type)
    encrypted = encrypt_config(data.config, sensitive)

    provider = PaymentProvider(
        provider_type=data.provider_type,
        display_name=data.display_name,
        status=data.status,
        config=encrypted,
        is_default=data.is_default,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)

    return _mask_provider(provider)


@router.put("/{provider_id}", response_model=dict)
def update_provider(
    provider_id: int,
    data: PaymentProviderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Update a payment provider. Re-encrypts config if changed."""
    provider = db.query(PaymentProvider).filter(
        PaymentProvider.id == provider_id
    ).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Payment provider not found")

    if data.display_name is not None:
        provider.display_name = data.display_name
    if data.status is not None:
        provider.status = data.status
    if data.is_default is not None:
        provider.is_default = data.is_default
    if data.config is not None:
        sensitive = get_sensitive_fields(provider.provider_type)
        # If a sensitive field is masked (starts with ****), keep the existing encrypted value
        existing_config = provider.config or {}
        new_config = dict(data.config)
        for field in sensitive:
            new_val = new_config.get(field, "")
            if isinstance(new_val, str) and new_val.startswith("****"):
                # Keep existing encrypted value
                new_config[field] = existing_config.get(field, "")
            elif new_val:
                # Encrypt the new value
                from app.core.encryption import encrypt_value
                new_config[field] = encrypt_value(new_val)
            # else: empty string, store as-is
        provider.config = new_config

    db.commit()
    db.refresh(provider)
    return _mask_provider(provider)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Delete a payment provider. Rejects if it has linked receipts."""
    provider = db.query(PaymentProvider).filter(
        PaymentProvider.id == provider_id
    ).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Payment provider not found")

    # Check for linked receipts
    receipt_count = db.query(Receipt).filter(
        Receipt.payment_provider_id == provider_id
    ).count() if hasattr(Receipt, "payment_provider_id") else 0

    if receipt_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete provider: {receipt_count} receipts are linked to it",
        )

    db.delete(provider)
    db.commit()


@router.post("/{provider_id}/toggle", response_model=dict)
def toggle_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Toggle provider status between active and disabled."""
    provider = db.query(PaymentProvider).filter(
        PaymentProvider.id == provider_id
    ).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Payment provider not found")

    if provider.status == "active":
        provider.status = "disabled"
    else:
        provider.status = "active"

    db.commit()
    db.refresh(provider)
    return _mask_provider(provider)


@router.post("/{provider_id}/test", response_model=dict)
def test_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Test provider configuration (local validation only, no external API calls)."""
    provider = db.query(PaymentProvider).filter(
        PaymentProvider.id == provider_id
    ).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Payment provider not found")

    # Decrypt config for validation
    sensitive = get_sensitive_fields(provider.provider_type)
    decrypted = decrypt_config(provider.config or {}, sensitive)

    adapter = LocalValidationAdapter(provider.provider_type, decrypted)
    result = adapter.test_connection()
    return result
