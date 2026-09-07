"""Reports endpoints — admin analytics aggregates."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.authorization import require_permission
from app.db.session import get_db
from app.domains.auth.models import User
from app.domains.reports.schemas import AnnualSummary, PaidTierWithoutPurchase
from app.domains.reports.service import annual_summary, paid_tier_without_purchase

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/annual-summary", response_model=AnnualSummary)
def get_annual_summary(
    year: int | None = Query(None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports.read")),
):
    """Annual financial + membership summary (defaults to the current year)."""
    return annual_summary(db, year or date.today().year)


@router.get("/paid-tier-without-purchase", response_model=PaidTierWithoutPurchase)
def get_paid_tier_without_purchase(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    # Named rows about individual members, and the fix is per member on their
    # own record — so this reads member data, not aggregates like the summary.
    current_user: User = Depends(require_permission("members.read")),
):
    """Members on a priced tier that no membership receipt has ever paid for."""
    return paid_tier_without_purchase(db, page, per_page)
