"""A member buying their own membership plan.

Separate from ``PUT /members/me`` on purpose. ``MemberSelfUpdate`` excludes
``membership_type_id`` because the tier sets the recurring fee and unlocks
restricted activities, and that guard stays: buying a plan has its own rules —
a price, a prorated first period, and a payment that has to arrive before
anything changes — none of which a profile update could enforce.

Nothing here takes a payment. The purchase raises an emitted receipt and hands
its id back; the portal then posts it to the Stripe or Redsys checkout that
already exists, restricts a member to their own receipts, and already has
working webhooks and return paths.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.authorization import require_permission
from app.core.db_utils import current_member_or_403
from app.db.session import get_db
from app.domains.auth.models import User
from app.domains.billing.membership_purchase_service import (
    MembershipQuote,
    purchase_membership,
    quote_membership_purchase,
)
from app.domains.billing.schemas import (
    MembershipPurchaseQuote,
    MembershipPurchaseRequest,
    MembershipPurchaseResponse,
)
from app.domains.members.models import MembershipType

router = APIRouter(prefix="/members/me/membership", tags=["members"])


def _membership_type(db: Session, membership_type_id: int) -> MembershipType:
    mtype = (
        db.query(MembershipType)
        .filter(MembershipType.id == membership_type_id)
        .first()
    )
    if not mtype:
        raise HTTPException(status_code=404, detail="Membership type not found")
    return mtype


def _quote_fields(quote: MembershipQuote) -> dict:
    mtype = quote.membership_type
    return {
        "membership_type_id": mtype.id,
        "membership_type_name": mtype.name,
        "billing_frequency": mtype.billing_frequency,
        "full_price": mtype.base_price,
        "base_amount": quote.base_amount,
        "vat_rate": quote.vat_rate,
        "vat_amount": quote.vat_amount,
        "total_amount": quote.total_amount,
        "is_prorated": quote.is_prorated,
        "period_start": quote.period_start,
        "period_end": quote.period_end,
        "months_charged": quote.months_charged,
        "months_in_period": quote.months_in_period,
    }


@router.get("/quote/{membership_type_id}", response_model=MembershipPurchaseQuote)
def quote_membership(
    membership_type_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("self.billing.read")),
):
    """Price a plan for the caller without raising anything.

    Refuses exactly what the purchase refuses, so a plan that cannot be bought
    cannot be quoted either and the portal never offers a price it would then
    reject.
    """
    member = current_member_or_403(db, current_user, active_only=True)
    mtype = _membership_type(db, membership_type_id)
    quote = quote_membership_purchase(db, member, mtype)
    return MembershipPurchaseQuote(**_quote_fields(quote))


@router.post(
    "/purchase",
    response_model=MembershipPurchaseResponse,
    status_code=status.HTTP_201_CREATED,
)
def purchase_membership_endpoint(
    data: MembershipPurchaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("self.billing.write")),
):
    """Buy a plan: raise the receipt, and leave the member on their current tier.

    The plan is granted when the receipt is paid, wherever the money comes from
    — card, cash recorded by an admin, or a SEPA collection reconciled days
    later. Any purchase still awaiting payment is voided by this one, so a
    member who picked the wrong plan can simply pick again.
    """
    member = current_member_or_403(db, current_user, active_only=True)
    mtype = _membership_type(db, data.membership_type_id)

    receipt, quote = purchase_membership(
        db, member, mtype, created_by_id=current_user.id
    )
    db.commit()
    db.refresh(receipt)

    return MembershipPurchaseResponse(
        **_quote_fields(quote),
        receipt_id=receipt.id,
        receipt_number=receipt.receipt_number,
        receipt_status=receipt.status,
        due_date=receipt.due_date,
    )
