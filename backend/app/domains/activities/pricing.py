"""What a member is charged for an activity price."""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.domains.activities.models import Activity, ActivityPrice
from app.domains.activities.schemas import ActivityPriceResponse
from app.domains.billing.service import activity_vat_rate, calculate_vat


def priced(db: Session, activity: Activity, price: ActivityPrice) -> ActivityPriceResponse:
    """Attach what the member will actually be charged to a stored base price.

    Every response carrying a price goes through here: the schema defaults the
    VAT fields to 0, so a price serialized straight from the row reads as free.
    """
    rate = activity_vat_rate(db, activity.tax_rate)
    vat, total = calculate_vat(Decimal(str(price.amount)), rate)
    return ActivityPriceResponse.model_validate(price).model_copy(
        update={
            "vat_rate": float(rate),
            "vat_amount": float(vat),
            "total_amount": float(total),
        }
    )
