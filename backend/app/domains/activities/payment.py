"""What the pay-to-confirm flow asks of an activity.

A ``legacy`` activity never reaches anything here: ``needs_payment`` is false for
it, and every other function is only called for a seat that needs payment.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.clock import org_timezone, org_today
from app.core.config import settings
from app.domains.activities.models import PAYMENT_FLOW_PAY_TO_CONFIRM, Activity
from app.domains.billing.payment_instructions import has_active_online_provider
from app.domains.billing.recurring_billing_service import membership_fee_due_days
from app.domains.billing.rules import billing_int_rule
from app.domains.organizations.models import OrganizationSettings

ONLINE_METHODS = frozenset({"card", "bizum"})


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


def receipt_due_date(db: Session, due_at: datetime | None) -> date:
    """The deadline when auto-cancel is on, else the club's usual due days."""
    if due_at is not None:
        return due_at.astimezone(org_timezone(db)).date()
    return org_today(db) + timedelta(days=membership_fee_due_days(db))


def unusable_methods(db: Session, methods: list[str]) -> list[str]:
    """The methods the club cannot take today: online needs a live provider,
    a transfer needs an IBAN to send it to."""
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    online = has_active_online_provider(db)
    unusable = []
    for method in methods:
        if method in ONLINE_METHODS and not online:
            unusable.append(method)
        elif method == "transfer" and not (org and org.bank_iban):
            unusable.append(method)
    return unusable


@dataclass(frozen=True)
class SeatPaymentInstructions:
    pay_now_url: str | None = None
    bank_details: str | None = None
    cash: bool = False


def seat_payment_instructions(
    db: Session, activity: Activity, locale: str
) -> SeatPaymentInstructions:
    """How the member may pay, from the methods the activity accepts."""
    methods = set(activity.payment_methods or [])
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    pay_now_url = None
    if methods & ONLINE_METHODS and has_active_online_provider(db):
        pay_now_url = f"{settings.FRONTEND_URL}/{locale}/my-receipts"
    bank_details = None
    if "transfer" in methods and org and org.bank_iban:
        bank_details = " — ".join(filter(None, [org.bank_name, org.bank_iban]))
    return SeatPaymentInstructions(
        pay_now_url=pay_now_url, bank_details=bank_details, cash="cash" in methods
    )
