"""Reports endpoints — admin analytics aggregates."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.authorization import require_permission
from app.db.session import get_db
from app.domains.auth.models import User
from app.domains.reports.schemas import AnnualSummary
from app.domains.reports.service import annual_summary

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/annual-summary", response_model=AnnualSummary)
def get_annual_summary(
    year: int | None = Query(None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("reports.read")),
):
    """Annual financial + membership summary (defaults to the current year)."""
    return annual_summary(db, year or date.today().year)
