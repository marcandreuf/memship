"""Activity price endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.authorization import require_admin
from app.core.db_utils import get_or_404
from app.core.security.dependencies import get_current_user
from app.db.session import get_db
from app.domains.activities.models import Activity, ActivityModality, ActivityPrice
from app.domains.activities.schemas import (
    ActivityPriceCreate,
    ActivityPriceResponse,
    ActivityPriceUpdate,
)
from app.domains.auth.models import User

router = APIRouter(prefix="/activities/{activity_id}/prices", tags=["activity-prices"])


@router.get("/", response_model=list[ActivityPriceResponse])
def list_prices(
    activity_id: int,
    modality_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_or_404(db, Activity, activity_id)
    query = db.query(ActivityPrice).filter(ActivityPrice.activity_id == activity_id)
    if modality_id is not None:
        query = query.filter(ActivityPrice.modality_id == modality_id)
    return query.order_by(ActivityPrice.display_order).all()


@router.post("/", response_model=ActivityPriceResponse, status_code=status.HTTP_201_CREATED)
def create_price(
    activity_id: int,
    data: ActivityPriceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    get_or_404(db, Activity, activity_id)

    # If modality_id provided, verify it belongs to the same activity
    if data.modality_id is not None:
        modality = db.query(ActivityModality).filter(
            ActivityModality.id == data.modality_id,
            ActivityModality.activity_id == activity_id,
        ).first()
        if not modality:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Modality does not belong to this activity",
            )

    price = ActivityPrice(activity_id=activity_id, **data.model_dump())
    db.add(price)
    db.commit()
    db.refresh(price)
    return price


@router.put("/{price_id}", response_model=ActivityPriceResponse)
def update_price(
    activity_id: int,
    price_id: int,
    data: ActivityPriceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    price = get_or_404(db, ActivityPrice, price_id)
    if price.activity_id != activity_id:
        raise HTTPException(status_code=404, detail="Price not found for this activity")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(price, key, value)
    db.commit()
    db.refresh(price)
    return price


@router.delete("/{price_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_price(
    activity_id: int,
    price_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    price = get_or_404(db, ActivityPrice, price_id)
    if price.activity_id != activity_id:
        raise HTTPException(status_code=404, detail="Price not found for this activity")
    db.delete(price)
    db.commit()
