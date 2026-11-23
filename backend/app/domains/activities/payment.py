"""What the pay-to-confirm flow asks of an activity.

A ``legacy`` activity never reaches anything here: ``needs_payment`` is false for
it, and every other function is only called for a seat that needs payment.

What is not specific to activities lives with the seat in ``billing``, where
space bookings use it too (#603): the methods a club can take, how a seat is
paid, and the receipt's due date. The activity code reaches it from here.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domains.activities.models import PAYMENT_FLOW_PAY_TO_CONFIRM, Activity
from app.domains.billing.payment_instructions import (  # noqa: F401
    seat_payment_instructions,
    unusable_methods,
)
from app.domains.billing.rules import billing_int_rule
from app.domains.billing.seats import receipt_due_date  # noqa: F401
from app.domains.organizations.models import OrganizationSettings


def needs_payment(activity: Activity, amount: Decimal | None) -> bool:
    """Whether a seat at ``amount`` is held as pending until paid.

    The one place the flow branches: a ``legacy`` activity and an exempt price
    are confirmed at once, as before.
    """
    return (
        activity.payment_flow == PAYMENT_FLOW_PAY_TO_CONFIRM
        and amount is not None
        and Decimal(str(amount)) > 0
    )


def _features(db: Session) -> dict:
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    return (org.features if org else None) or {}


def auto_cancel_hours(db: Session, activity: Activity) -> int | None:
    """How long an unpaid seat is held, or None when auto-cancel is off.

    The activity's override wins; a NULL on the activity inherits the club's.
    """
    features = _features(db)
    enabled = activity.auto_cancel_enabled
    if enabled is None:
        enabled = features.get("activity_auto_cancel_enabled") is True
    if not enabled:
        return None
    if activity.auto_cancel_hours is not None:
        return activity.auto_cancel_hours
    return billing_int_rule(features, "activity_auto_cancel_hours")


def payment_due_at(db: Session, activity: Activity, now: datetime) -> datetime | None:
    hours = auto_cancel_hours(db, activity)
    return None if hours is None else now + timedelta(hours=hours)
