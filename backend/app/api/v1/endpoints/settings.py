"""Organization settings endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.authorization import require_super_admin
from app.core.security.dependencies import get_current_user
from app.db.session import get_db
from app.domains.auth.models import User
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
