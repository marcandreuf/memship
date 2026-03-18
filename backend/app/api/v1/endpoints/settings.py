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
