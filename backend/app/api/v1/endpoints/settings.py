"""Organization settings endpoints."""

import copy

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.authorization import require_permission
from app.core.config import settings as app_settings
from app.core.security import secrets_crypto
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
from app.core.email import send_test_email
from app.domains.mailing.mailing_config import (
    PROVIDER_FIELDS as MAIL_PROVIDER_FIELDS,
    build_field_node as build_mail_field_node,
    resolve_mailing_config,
)
from app.domains.mailing.mailing_schemas import (
    MailGmailView,
    MailingConfigUpdate,
    MailingConfigView,
    MailingTestRequest,
    MailingTestResult,
    MailResendView,
    MailSecretStatus,
    MailSecretUpdate,
)
from app.domains.organizations.models import OrganizationSettings
from app.domains.organizations.schemas import (
    OrganizationBrandingResponse,
    OrganizationSettingsResponse,
    OrganizationSettingsUpdate,
)
from app.domains.organizations.address_schemas import (
    OrganizationAddressResponse,
    OrganizationAddressUpdate,
)
from app.domains.persons.models import Address

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/branding", response_model=OrganizationBrandingResponse)
def get_branding(db: Session = Depends(get_db)):
    """The portal shell's identity: name, logo, colour, contact block, feature
    flags. Unauthenticated on purpose — the shell renders it around the login
    form, and none of it is private. `settings.read` guards the rest.
    """
    return db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()


@router.get("/", response_model=OrganizationSettingsResponse)
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.read")),
):
    return db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()


@router.put("/", response_model=OrganizationSettingsResponse)
def update_settings(
    data: OrganizationSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.write")),
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
    current_user: User = Depends(require_permission("settings.read")),
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
    current_user: User = Depends(require_permission("settings.write")),
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
    current_user: User = Depends(require_permission("settings.integrations.write")),
):
    """Masked SSO configuration for the settings screen. Never returns secrets."""
    return _build_sso_view(db)


@router.put("/sso", response_model=SsoConfigView)
def update_sso_config(
    data: SsoConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.integrations.write")),
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


# --- Mailing provider configuration (super_admin only) ---
#
# Exactly one provider is active at a time; ``active_provider`` selects it. The
# machinery mirrors the SSO config above (masked GET, write-only secrets,
# DB-then-env resolution) with the one-of-N active-provider rule on top.


def _build_mailing_view(db: Session) -> MailingConfigView:
    resolved = resolve_mailing_config(db)
    r, g = resolved.resend, resolved.gmail
    return MailingConfigView(
        active_provider=resolved.active,
        resend=MailResendView(
            from_email=r.get("from_email"),
            api_key=MailSecretStatus(
                configured=r.configured("api_key"),
                last4=r.last4("api_key"),
            ),
            ready=r.ready,
        ),
        gmail=MailGmailView(
            user=g.get("user"),
            from_email=g.get("from_email"),
            app_password=MailSecretStatus(
                configured=g.configured("app_password"),
                last4=g.last4("app_password"),
            ),
            ready=g.ready,
        ),
        secrets_encryption_available=secrets_crypto.secrets_available(),
        sources=resolved.flat_sources(),
    )


def _apply_mail_provider_update(pname: str, pupdate, node: dict, changed: list[str]) -> None:
    """Merge one provider's update into its JSONB node.

    Blank secret = unchanged; ``clear`` wipes; a secret write requires the
    encryption key. Non-secret strings clear on ``""`` and set otherwise.
    """
    for spec in MAIL_PROVIDER_FIELDS[pname]:
        field_update = getattr(pupdate, spec.name)
        if field_update is None:
            continue

        if isinstance(field_update, MailSecretUpdate):
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
                        detail={"code": "mailing_encryption_key_missing"},
                    )
                node[spec.name] = build_mail_field_node(field_update.value, secret)
                changed.append(f"{pname}.{spec.name}")
            # value None/empty and not clearing → leave the stored secret untouched
        else:  # non-secret string field
            if field_update == "":
                if node.pop(spec.name, None) is not None:
                    changed.append(f"{pname}.{spec.name}")
            else:
                node[spec.name] = {"value": field_update, "secret": False}
                changed.append(f"{pname}.{spec.name}")


@router.get("/mailing", response_model=MailingConfigView)
def get_mailing_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.integrations.write")),
):
    """Masked mailing configuration for the settings screen. Never returns secrets."""
    return _build_mailing_view(db)


@router.put("/mailing", response_model=MailingConfigView)
def update_mailing_config(
    data: MailingConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.integrations.write")),
):
    settings_obj = (
        db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    )
    config = copy.deepcopy(settings_obj.mailing_config or {})
    changed: list[str] = []

    for pname, pupdate in (("resend", data.resend), ("gmail", data.gmail)):
        if pupdate is None:
            continue
        node = config.setdefault(pname, {})
        _apply_mail_provider_update(pname, pupdate, node, changed)

    # Apply credential changes to the in-session object before the readiness
    # check so resolve_mailing_config sees them (same identity-mapped row). On a
    # rejected activation, restore the original value rather than rolling back
    # the whole session.
    original = settings_obj.mailing_config
    settings_obj.mailing_config = config

    if "active_provider" in data.model_fields_set:
        ap = data.active_provider
        if ap is not None:
            resolved = resolve_mailing_config(db)
            provider = resolved.provider(ap)
            if provider is None or not provider.ready:
                settings_obj.mailing_config = original
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": "mailing_provider_not_ready"},
                )
        if config.get("active_provider") != ap:
            config["active_provider"] = ap
            changed.append("active_provider")

    settings_obj.mailing_config = config

    if changed:
        db.add(
            AuditLog(
                table_name="organization_settings",
                record_id=1,
                action="update",
                user_id=current_user.id,
                changed_fields=[f"mailing_config.{c}" for c in changed],
            )
        )

    db.commit()
    return _build_mailing_view(db)


@router.post("/mailing/test", response_model=MailingTestResult)
def test_mailing_provider(
    data: MailingTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings.integrations.write")),
):
    """Send a test email through a specific provider, bypassing ``active_provider``.

    Lets the superadmin verify credentials before switching the active provider.
    A transport failure is returned as ``{ok: false, error}`` (200), not an HTTP
    error; missing credentials for the provider yield 400.
    """
    resolved = resolve_mailing_config(db)
    provider = resolved.provider(data.provider)
    if provider is None or not provider.ready:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "mailing_provider_not_ready"},
        )

    to = (data.to or "").strip() or (current_user.email or "").strip()
    if not to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "mailing_test_no_recipient"},
        )

    locale = getattr(current_user, "preferred_locale", None) or app_settings.DEFAULT_LOCALE
    ok, error = send_test_email(resolved, data.provider, to, locale)
    return MailingTestResult(ok=ok, error=error)
