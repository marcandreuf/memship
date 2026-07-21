"""Organization settings endpoints."""

import copy

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.authorization import require_super_admin
from app.core.config import settings as app_settings
from app.core.security import secrets_crypto
from app.core.security.dependencies import get_current_user
from app.core.security.oauth import provider_redirect_uri
from app.db.session import get_db
from app.domains.audit.models import AuditLog
from app.domains.auth.models import User
from app.domains.auth.sso_config import (
    PROVIDER_FIELDS,
    build_field_node,
    resolve_sso_config,
)
from app.domains.auth.sso_schemas import (
    SsoAppleView,
    SsoConfigUpdate,
    SsoConfigView,
    SsoGoogleView,
    SsoSecretStatus,
    SsoSecretUpdate,
)
from app.domains.organizations.models import OrganizationSettings
from app.domains.organizations.schemas import (
    OrganizationSettingsResponse,
    OrganizationSettingsUpdate,
)
from app.domains.organizations.address_schemas import (
    OrganizationAddressResponse,
    OrganizationAddressUpdate,
)
from app.domains.persons.models import Address

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/", response_model=OrganizationSettingsResponse)
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()


@router.put("/", response_model=OrganizationSettingsResponse)
def update_settings(
    data: OrganizationSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    settings_obj = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(settings_obj, key, value)
    db.commit()
    db.refresh(settings_obj)
    return settings_obj


@router.get("/address", response_model=OrganizationAddressResponse | None)
def get_organization_address(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the organization's address."""
    return (
        db.query(Address)
        .filter(
            Address.entity_type == "organization",
            Address.entity_id == 1,
            Address.is_active.is_(True),
        )
        .first()
    )


@router.put("/address", response_model=OrganizationAddressResponse)
def update_organization_address(
    data: OrganizationAddressUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Create or update the organization's address."""
    address = (
        db.query(Address)
        .filter(
            Address.entity_type == "organization",
            Address.entity_id == 1,
        )
        .first()
    )

    if address:
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(address, key, value)
    else:
        address = Address(
            entity_type="organization",
            entity_id=1,
            is_primary=True,
            **data.model_dump(),
        )
        db.add(address)

    db.commit()
    db.refresh(address)
    return address


# --- Single sign-on configuration (super_admin only) ---


def _build_sso_view(db: Session) -> SsoConfigView:
    resolved = resolve_sso_config(db)
    g, a = resolved.google, resolved.apple
    return SsoConfigView(
        google=SsoGoogleView(
            enabled=g.enabled,
            client_id=g.get("client_id"),
            client_secret=SsoSecretStatus(
                configured=g.configured("client_secret"),
                last4=g.last4("client_secret"),
            ),
            ready=g.ready,
        ),
        apple=SsoAppleView(
            enabled=a.enabled,
            client_id=a.get("client_id"),
            team_id=a.get("team_id"),
            key_id=a.get("key_id"),
            private_key=SsoSecretStatus(
                configured=a.configured("private_key"),
                last4=a.last4("private_key"),
            ),
            ready=a.ready,
        ),
        backend_public_url=app_settings.BACKEND_PUBLIC_URL,
        redirect_uris={
            "google": provider_redirect_uri("google"),
            "apple": provider_redirect_uri("apple"),
        },
        secrets_encryption_available=secrets_crypto.secrets_available(),
        sources=resolved.flat_sources(),
    )


def _apply_provider_update(pname: str, pupdate, node: dict, changed: list[str]) -> None:
    """Merge one provider's update into its JSONB node.

    Blank secret = unchanged; ``clear`` wipes; a secret write requires the
    encryption key. Non-secret strings clear on ``""`` and set otherwise.
    """
    if pupdate.enabled is not None and node.get("enabled") != pupdate.enabled:
        node["enabled"] = pupdate.enabled
        changed.append(f"{pname}.enabled")

    for spec in PROVIDER_FIELDS[pname]:
        field_update = getattr(pupdate, spec.name)
        if field_update is None:
            continue

        if isinstance(field_update, SsoSecretUpdate):
            if field_update.clear:
                if node.pop(spec.name, None) is not None:
                    changed.append(f"{pname}.{spec.name}")
            elif field_update.value:
                secret = (
                    field_update.secret
                    if field_update.secret is not None
                    else spec.secret_default
                )
                if secret and not secrets_crypto.secrets_available():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={"code": "sso_encryption_key_missing"},
                    )
                node[spec.name] = build_field_node(field_update.value, secret)
                changed.append(f"{pname}.{spec.name}")
            # value None/empty and not clearing → leave the stored secret untouched
        else:  # non-secret string field
            if field_update == "":
                if node.pop(spec.name, None) is not None:
                    changed.append(f"{pname}.{spec.name}")
            else:
                node[spec.name] = {"value": field_update, "secret": False}
                changed.append(f"{pname}.{spec.name}")


@router.get("/sso", response_model=SsoConfigView)
def get_sso_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Masked SSO configuration for the settings screen. Never returns secrets."""
    return _build_sso_view(db)


@router.put("/sso", response_model=SsoConfigView)
def update_sso_config(
    data: SsoConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    settings_obj = (
        db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    )
    config = copy.deepcopy(settings_obj.sso_config or {})
    changed: list[str] = []

    for pname, pupdate in (("google", data.google), ("apple", data.apple)):
        if pupdate is None:
            continue
        node = config.setdefault(pname, {})
        _apply_provider_update(pname, pupdate, node, changed)

    settings_obj.sso_config = config

    if changed:
        # Record the change without ever persisting the values themselves.
        db.add(
            AuditLog(
                table_name="organization_settings",
                record_id=1,
                action="update",
                user_id=current_user.id,
                changed_fields=[f"sso_config.{c}" for c in changed],
            )
        )

    db.commit()
    return _build_sso_view(db)
