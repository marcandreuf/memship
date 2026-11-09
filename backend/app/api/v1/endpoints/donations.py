"""A member donating from the portal.

Two routes, both member-facing and both behind ``features.member_donations_enabled``.
They answer **404** when it is off, like every other module gate: an instance
that does not take donations should not advertise that the feature exists.

Nothing here takes a payment. ``POST`` raises an emitted donation receipt and
hands its id back; the portal then posts it to the Stripe or Redsys checkout
that already exists, restricts a member to their own receipts, and already has
working webhooks and return paths. ``members/me/membership`` is the same shape
for the same reason (#434).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.authorization import require_permission
from app.core.db_utils import current_member_or_403
from app.db.session import get_db
from app.domains.auth.models import User
from app.domains.billing.donation_service import (
    create_donation,
    donation_options,
    member_donations_enabled,
)
from app.domains.billing.schemas import (
    DonationOptionsResponse,
    DonationRequest,
    DonationResponse,
)

router = APIRouter(prefix="/members/me/donations", tags=["members"])


def _require_donations_enabled(db: Session) -> None:
    if not member_donations_enabled(db):
        raise HTTPException(status_code=404, detail="Not found")


@router.get("/options", response_model=DonationOptionsResponse)
def get_donation_options(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("self.billing.read")),
):
    """What this organisation asks for, and the amounts it will accept.

    Resolved per request rather than cached: the message and both bounds are
    settings an administrator can change while a member has the page open, and
    the page offering an amount the ``POST`` would then refuse is the one
    inconsistency worth a round trip.
    """
    _require_donations_enabled(db)
    current_member_or_403(db, current_user, active_only=True)
    options = donation_options(db)
    return DonationOptionsResponse(
        message=options.message,
        min_amount=options.min_amount,
        max_amount=options.max_amount,
        suggested_amounts=options.suggested_amounts,
    )


@router.post("/", response_model=DonationResponse, status_code=status.HTTP_201_CREATED)
def create_donation_endpoint(
    data: DonationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("self.billing.write")),
):
    """Raise the receipt for a donation the member has chosen the size of.

    The amount is checked against the configured bounds here, not only in the
    browser: it arrives from the client, and the bounds are what stop a typo
    becoming a charge nobody meant to make.

    An earlier unpaid donation is left alone rather than voided — two donations
    are two donations, unlike two membership purchases — and whichever one is
    abandoned is voided on its due date by ``expire_unpaid_donations``.
    """
    _require_donations_enabled(db)
    member = current_member_or_403(db, current_user, active_only=True)

    receipt = create_donation(db, member, data.amount, created_by_id=current_user.id)
    db.commit()
    db.refresh(receipt)

    return DonationResponse(
        receipt_id=receipt.id,
        receipt_number=receipt.receipt_number,
        receipt_status=receipt.status,
        total_amount=receipt.total_amount,
        due_date=receipt.due_date,
    )
