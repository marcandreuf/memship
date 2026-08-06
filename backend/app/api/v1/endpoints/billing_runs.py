"""Billing run endpoints — manual trigger and run history (admin only)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.authorization import require_permission
from app.core.pagination import paginate
from app.db.session import get_db
from app.domains.auth.models import User
from app.domains.billing.models import BillingRun
from app.domains.billing.recurring_billing_service import (
    BILLABLE_FREQUENCIES,
    run_billing,
)
from app.domains.billing.schemas import BillingRunResponse, RunNowRequest

router = APIRouter(prefix="/billing-runs", tags=["billing-runs"])


@router.post("/run-now")
def run_now(
    data: RunNowRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("billing.run")),
):
    """Manually trigger recurring billing now.

    Omit ``frequency`` to run every billable frequency for its current period;
    pass a specific one to run only that. Idempotent per period — re-running the
    same period generates no additional receipts.
    """
    frequencies = (
        [data.frequency] if data.frequency else list(BILLABLE_FREQUENCIES)
    )
    runs = [
        run_billing(db, frequency, "manual", user_id=current_user.id)
        for frequency in frequencies
    ]
    db.commit()
    return {
        "runs": [BillingRunResponse.model_validate(r).model_dump() for r in runs],
        "receipts_generated": sum(r.receipts_generated for r in runs),
    }


@router.get("")
def list_billing_runs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("billing.read")),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    frequency: str | None = Query(None),
    run_status: str | None = Query(None, alias="status"),
):
    """Paginated run history, newest first, optionally filtered by frequency/status."""
    query = db.query(BillingRun)
    if frequency:
        query = query.filter(BillingRun.frequency == frequency)
    if run_status:
        query = query.filter(BillingRun.status == run_status)
    query = query.order_by(BillingRun.started_at.desc(), BillingRun.id.desc())

    items, meta = paginate(query, page, per_page)
    return {
        "items": [BillingRunResponse.model_validate(r).model_dump() for r in items],
        "meta": meta.model_dump(),
    }


@router.get("/{run_id}")
def get_billing_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("billing.read")),
):
    """Single run detail, including the per-member error list."""
    run = db.query(BillingRun).filter(BillingRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Billing run not found")
    return BillingRunResponse.model_validate(run).model_dump()
