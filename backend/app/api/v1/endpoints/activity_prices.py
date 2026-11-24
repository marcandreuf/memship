"""Activity price endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.authorization import require_any_permission, require_permission
from app.core.db_utils import get_or_404
from app.db.session import get_db
from app.domains.activities.models import Activity, ActivityModality, ActivityPrice
from app.domains.activities.pricing import priced, prices_for_viewer
from app.domains.activities.schemas import (
    ActivityPriceCreate,
    ActivityPriceResponse,
    ActivityPriceUpdate,
)
from app.domains.activities.service import get_visible_activity_or_404
from app.domains.auth.models import User

router = APIRouter(prefix="/activities/{activity_id}/prices", tags=["activity-prices"])


def _take_the_default(db: Session, activity_id: int, keep_id: int | None = None) -> None:
    """Move the default to the price being written, clearing any other holder.

    ``uq_activity_prices_is_default`` refuses a second default per activity, so
    without this the admin's second "make this the default" reaches them as a
    500 with nothing to act on. Same shape as membership types, which clear the
    previous default the same way, except that there the flag is instance-wide
    and here it is per activity.

    Clearing the last default outright is allowed, unlike membership types
    where sign-ups would be left with no tier: an activity with no default
    preselects nothing on the registration page, which is what every activity
    did before the flag meant anything (memship#601).
    """
    others = db.query(ActivityPrice).filter(
        ActivityPrice.activity_id == activity_id,
        ActivityPrice.is_default == True,  # noqa: E712 -- SQL boolean, not Python
    )
    if keep_id is not None:
        others = others.filter(ActivityPrice.id != keep_id)
    others.update({"is_default": False}, synchronize_session=False)
    db.flush()


@router.get("/", response_model=list[ActivityPriceResponse])
def list_prices(
    activity_id: int,
    modality_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("activities.read", "self.activities.read")),
):
    activity = get_visible_activity_or_404(db, activity_id, current_user)
    query = db.query(ActivityPrice).filter(ActivityPrice.activity_id == activity_id)
    if modality_id is not None:
        query = query.filter(ActivityPrice.modality_id == modality_id)
    rows = query.order_by(ActivityPrice.display_order).all()
    # Same narrowing as the activity detail response: this route carries the
    # same pair of permissions, so without it a member could read the prices
    # their type is excluded from by asking for them directly (#427).
    return [
        priced(db, activity, p)
        for p in prices_for_viewer(db, activity, current_user, rows)
    ]


@router.post("/", response_model=ActivityPriceResponse, status_code=status.HTTP_201_CREATED)
def create_price(
    activity_id: int,
    data: ActivityPriceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("activities.write")),
):
    activity = get_or_404(db, Activity, activity_id)

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

    if data.is_default:
        _take_the_default(db, activity_id)

    price = ActivityPrice(activity_id=activity_id, **data.model_dump())
    db.add(price)
    db.commit()
    db.refresh(price)
    return priced(db, activity, price)


@router.put("/{price_id}", response_model=ActivityPriceResponse)
def update_price(
    activity_id: int,
    price_id: int,
    data: ActivityPriceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("activities.write")),
):
    activity = get_or_404(db, Activity, activity_id)
    price = get_or_404(db, ActivityPrice, price_id)
    if price.activity_id != activity_id:
        raise HTTPException(status_code=404, detail="Price not found for this activity")

    update_data = data.model_dump(exclude_unset=True)
    if update_data.get("is_default") and not price.is_default:
        _take_the_default(db, activity_id, keep_id=price.id)
    for key, value in update_data.items():
        setattr(price, key, value)
    db.commit()
    db.refresh(price)
    return priced(db, activity, price)


@router.delete("/{price_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_price(
    activity_id: int,
    price_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("activities.write")),
):
    price = get_or_404(db, ActivityPrice, price_id)
    if price.activity_id != activity_id:
        raise HTTPException(status_code=404, detail="Price not found for this activity")
    db.delete(price)
    db.commit()
