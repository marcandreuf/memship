"""Discount code service — validation and application logic."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.money import round_money
from app.domains.activities.discount_schemas import normalize_code
from app.domains.activities.models import DiscountCode


class DiscountError(Exception):
    """Raised when a discount operation fails."""
    pass


def validate_discount_code(
    db: Session, activity_id: int, code: str, *, for_update: bool = False
) -> DiscountCode:
    """Validate a discount code for an activity. Returns the code or raises DiscountError.

    ``for_update`` locks the row for the rest of the transaction. A caller that
    goes on to redeem the code needs it: the ``max_uses`` check here and the
    increment in ``increment_usage`` are a read-modify-write on
    ``current_uses``, and without the lock two registrations arriving together
    both pass the check and the cap is exceeded by one. The preview endpoint
    only reads, so it leaves the row unlocked.
    """
    query = db.query(DiscountCode).filter(
        DiscountCode.activity_id == activity_id,
        DiscountCode.code == normalize_code(code),
        DiscountCode.is_active.is_(True),
    )
    if for_update:
        # populate_existing: the row may already be in the session from an
        # earlier read, and without it the locked SELECT would hand back the
        # stale in-memory counter instead of the one just read under the lock.
        query = query.with_for_update().populate_existing()
    discount = query.first()
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
    return max(Decimal("0"), round_money(result))


def increment_usage(db: Session, discount: DiscountCode) -> None:
    """Count one redemption. The row must be locked — see validate_discount_code."""
    discount.current_uses = (discount.current_uses or 0) + 1


def release_usage(db: Session, discount_id: int) -> None:
    """Give back the use a cancelled registration took, so the code can be
    redeemed by someone else. Locks the row itself: cancellation does not
    come through validate_discount_code."""
    discount = (
        db.query(DiscountCode)
        .filter(DiscountCode.id == discount_id)
        .with_for_update()
        .first()
    )
    if discount is not None:
        discount.current_uses = max(0, (discount.current_uses or 0) - 1)


def retake_usage(db: Session, discount_id: int) -> None:
    """Count the use again when a cancelled registration is reinstated by an
    admin. No cap check: the admin is overriding, and the seat is theirs to give."""
    discount = (
        db.query(DiscountCode)
        .filter(DiscountCode.id == discount_id)
        .with_for_update()
        .first()
    )
    if discount is not None:
        discount.current_uses = (discount.current_uses or 0) + 1
