"""Discount code endpoints."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.authorization import require_any_permission, require_permission
from app.core.db_utils import get_or_404
from app.core.security.dependencies import get_current_user
from app.db.session import get_db
from app.domains.activities.discount_schemas import (
    DiscountCodeCreate,
    DiscountCodeResponse,
    DiscountCodeUpdate,
    ValidateDiscountRequest,
    ValidateDiscountResponse,
)
from app.domains.activities.discount_service import (
    DiscountError,
    apply_discount,
    validate_discount_code,
)
from app.domains.activities.models import Activity, ActivityPrice, DiscountCode
from app.domains.auth.models import User
from app.domains.billing.service import activity_vat_rate, calculate_vat

router = APIRouter(prefix="/activities/{activity_id}/discount-codes", tags=["discount-codes"])


@router.get("/", response_model=list[DiscountCodeResponse])
def list_discount_codes(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("activities.read")),
):
    """List discount codes for an activity (admin only)."""
    get_or_404(db, Activity, activity_id)
    return (
        db.query(DiscountCode)
        .filter(DiscountCode.activity_id == activity_id)
        .order_by(DiscountCode.created_at.desc(), DiscountCode.id.desc())
        .all()
    )


@router.post("/", response_model=DiscountCodeResponse, status_code=status.HTTP_201_CREATED)
def create_discount_code(
    activity_id: int,
    data: DiscountCodeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("activities.write")),
):
    """Create a discount code for an activity (admin only)."""
    get_or_404(db, Activity, activity_id)

    # Check uniqueness
    existing = (
        db.query(DiscountCode)
        .filter(
            DiscountCode.activity_id == activity_id,
            DiscountCode.code == data.code,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A discount code with this code already exists for this activity",
        )

    discount = DiscountCode(activity_id=activity_id, **data.model_dump())
    db.add(discount)
    db.commit()
    db.refresh(discount)
    return discount


@router.put("/{code_id}", response_model=DiscountCodeResponse)
def update_discount_code(
    activity_id: int,
    code_id: int,
    data: DiscountCodeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("activities.write")),
):
    """Update a discount code (admin only)."""
    discount = get_or_404(db, DiscountCode, code_id)
    if discount.activity_id != activity_id:
        raise HTTPException(status_code=404, detail="Discount code not found for this activity")

    update_data = data.model_dump(exclude_unset=True)

    # If changing code, check uniqueness
    if "code" in update_data and update_data["code"] != discount.code:
        existing = (
            db.query(DiscountCode)
            .filter(
                DiscountCode.activity_id == activity_id,
                DiscountCode.code == update_data["code"],
                DiscountCode.id != code_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A discount code with this code already exists for this activity",
            )

    for key, value in update_data.items():
        setattr(discount, key, value)
    db.commit()
    db.refresh(discount)
    return discount


@router.delete("/{code_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_discount_code(
    activity_id: int,
    code_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("activities.write")),
):
    """Delete a discount code (admin only)."""
    discount = get_or_404(db, DiscountCode, code_id)
    if discount.activity_id != activity_id:
        raise HTTPException(status_code=404, detail="Discount code not found for this activity")
    db.delete(discount)
    db.commit()


# Validate endpoint — separate router to avoid prefix nesting issues
validate_router = APIRouter(tags=["discount-codes"])


@validate_router.post(
    "/activities/{activity_id}/validate-discount",
    response_model=ValidateDiscountResponse,
)
def validate_discount(
    activity_id: int,
    data: ValidateDiscountRequest,
    price_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("activities.read", "self.activities.read")),
):
    """Validate a discount code and return the discount preview."""
    activity = get_or_404(db, Activity, activity_id)

    try:
        discount = validate_discount_code(db, activity_id, data.code)
    except DiscountError as e:
        return ValidateDiscountResponse(valid=False, error=str(e))

    # If price_id provided, calculate discounted amount
    original_amount = None
    discounted_amount = None
    original_total = None
    discounted_total = None
    if price_id:
        price = (
            db.query(ActivityPrice)
            .filter(
                ActivityPrice.id == price_id,
                ActivityPrice.activity_id == activity_id,
            )
            .first()
        )
        if price:
            base = Decimal(str(price.amount))
            discounted = apply_discount(base, discount)
            original_amount = float(base)
            discounted_amount = float(discounted)
            # Same rate the receipt will carry, so the preview and the invoice
            # cannot disagree.
            rate = activity_vat_rate(db, activity.tax_rate)
            original_total = float(calculate_vat(base, rate)[1])
            discounted_total = float(calculate_vat(discounted, rate)[1])

    return ValidateDiscountResponse(
        valid=True,
        discount_type=discount.discount_type,
        discount_value=float(discount.discount_value),
        original_amount=original_amount,
        discounted_amount=discounted_amount,
        original_total=original_total,
        discounted_total=discounted_total,
    )
