"""Activity consent endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.authorization import require_admin
from app.core.db_utils import get_or_404
from app.core.security.dependencies import get_current_user
from app.db.session import get_db
from app.domains.activities.consent_schemas import (
    ActivityConsentCreate,
    ActivityConsentResponse,
    ActivityConsentUpdate,
)
from app.domains.activities.models import Activity, ActivityConsent
from app.domains.auth.models import User

router = APIRouter(prefix="/activities/{activity_id}/consents", tags=["activity-consents"])


@router.get("/", response_model=list[ActivityConsentResponse])
def list_consents(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List consents for an activity (all authenticated users)."""
    get_or_404(db, Activity, activity_id)
    return (
        db.query(ActivityConsent)
        .filter(
            ActivityConsent.activity_id == activity_id,
            ActivityConsent.is_active.is_(True),
        )
        .order_by(ActivityConsent.display_order)
        .all()
    )


@router.post("/", response_model=ActivityConsentResponse, status_code=status.HTTP_201_CREATED)
def create_consent(
    activity_id: int,
    data: ActivityConsentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a consent for an activity (admin only)."""
    get_or_404(db, Activity, activity_id)
    consent = ActivityConsent(activity_id=activity_id, **data.model_dump())
    db.add(consent)
    db.commit()
    db.refresh(consent)
    return consent


@router.put("/{consent_id}", response_model=ActivityConsentResponse)
def update_consent(
    activity_id: int,
    consent_id: int,
    data: ActivityConsentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update a consent (admin only)."""
    consent = get_or_404(db, ActivityConsent, consent_id)
    if consent.activity_id != activity_id:
        raise HTTPException(status_code=404, detail="Consent not found for this activity")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(consent, key, value)
    db.commit()
    db.refresh(consent)
    return consent


@router.delete("/{consent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_consent(
    activity_id: int,
    consent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete a consent (admin only)."""
    consent = get_or_404(db, ActivityConsent, consent_id)
    if consent.activity_id != activity_id:
        raise HTTPException(status_code=404, detail="Consent not found for this activity")
    db.delete(consent)
    db.commit()
