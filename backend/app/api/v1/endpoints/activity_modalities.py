"""Activity modality endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.authorization import require_admin
from app.core.db_utils import get_or_404
from app.core.security.dependencies import get_current_user
from app.db.session import get_db
from app.domains.activities.models import Activity, ActivityModality
from app.domains.activities.schemas import (
    ActivityModalityCreate,
    ActivityModalityResponse,
    ActivityModalityUpdate,
)
from app.domains.auth.models import User

router = APIRouter(prefix="/activities/{activity_id}/modalities", tags=["activity-modalities"])


@router.get("/", response_model=list[ActivityModalityResponse])
def list_modalities(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_or_404(db, Activity, activity_id)
    return (
        db.query(ActivityModality)
        .filter(ActivityModality.activity_id == activity_id)
        .order_by(ActivityModality.display_order)
        .all()
    )


@router.post("/", response_model=ActivityModalityResponse, status_code=status.HTTP_201_CREATED)
def create_modality(
    activity_id: int,
    data: ActivityModalityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    get_or_404(db, Activity, activity_id)

    # Check unique name per activity
    existing = (
        db.query(ActivityModality)
        .filter(
            ActivityModality.activity_id == activity_id,
            ActivityModality.name == data.name,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Modality with name '{data.name}' already exists for this activity",
        )

    modality = ActivityModality(activity_id=activity_id, **data.model_dump())
    db.add(modality)
    db.commit()
    db.refresh(modality)
    return modality


@router.put("/{modality_id}", response_model=ActivityModalityResponse)
def update_modality(
    activity_id: int,
    modality_id: int,
    data: ActivityModalityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    modality = get_or_404(db, ActivityModality, modality_id)
    if modality.activity_id != activity_id:
        raise HTTPException(status_code=404, detail="Modality not found for this activity")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(modality, key, value)
    db.commit()
    db.refresh(modality)
    return modality


@router.delete("/{modality_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_modality(
    activity_id: int,
    modality_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    modality = get_or_404(db, ActivityModality, modality_id)
    if modality.activity_id != activity_id:
        raise HTTPException(status_code=404, detail="Modality not found for this activity")
    db.delete(modality)
    db.commit()
