"""Discount code service — validation and application logic."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domains.activities.models import DiscountCode


class DiscountError(Exception):
    """Raised when a discount operation fails."""
    pass


def validate_discount_code(
    db: Session, activity_id: int, code: str
) -> DiscountCode:
    """Validate a discount code for an activity. Returns the code or raises DiscountError."""
    discount = (
        db.query(DiscountCode)
        .filter(
            DiscountCode.activity_id == activity_id,
            DiscountCode.code == code,
            DiscountCode.is_active.is_(True),
        )
        .first()
    )
    if not discount:
        raise DiscountError("Discount code not found")

    now = datetime.now(timezone.utc)

    if discount.valid_from and now < discount.valid_from:
        raise DiscountError("Discount code is not yet active")

    if discount.valid_until and now > discount.valid_until:
        raise DiscountError("Discount code has expired")

    if discount.max_uses is not None and (discount.current_uses or 0) >= discount.max_uses:
        raise DiscountError("Discount code has reached maximum uses")

    return discount


def apply_discount(price_amount: Decimal, discount: DiscountCode) -> Decimal:
    """Apply a discount to a price amount. Returns the discounted amount."""
    if discount.discount_type == "percentage":
        reduction = price_amount * discount.discount_value / Decimal("100")
        result = price_amount - reduction
    else:  # fixed
        result = price_amount - discount.discount_value

    # Never go below zero
    return max(Decimal("0"), result.quantize(Decimal("0.01")))


def increment_usage(db: Session, discount: DiscountCode) -> None:
    """Increment the usage counter for a discount code."""
    discount.current_uses = (discount.current_uses or 0) + 1
