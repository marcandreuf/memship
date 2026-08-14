"""Recurring billing service — calendar-period computation, run logging, dedup.

The heavy lifting (skip-if-exists, concept caching, VAT) lives in
``generate_membership_fees``. This module only:

- computes the calendar period for a frequency,
- decides which frequencies are due on a given day,
- wraps the fee generation in a ``BillingRun`` audit row that is idempotent per
  ``(frequency, period_start, period_end)``.

Only ``monthly`` / ``quarterly`` / ``annual`` are auto-billed. ``one_time``
membership types are never billed here.
"""

import calendar
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domains.billing.models import BillingRun
from app.domains.billing.schemas import GenerateMembershipFeesRequest
from app.domains.billing.service import generate_membership_fees
from app.domains.organizations.models import OrganizationSettings

# Frequencies eligible for automatic recurring billing (one_time excluded).
BILLABLE_FREQUENCIES = ("monthly", "quarterly", "annual")

# Days between emission and the due date of an automatically generated fee.
# Overridable per install with the ``recurring_billing_due_days`` feature key.
# A fee generated without a due date can never fall overdue, so no reminder is
# ever sent for it — the dunning pipeline keys entirely off ``due_date``.
DEFAULT_DUE_DAYS = 30

# First month (1-based) of each calendar quarter.
QUARTER_START_MONTHS = (1, 4, 7, 10)


def _last_day_of_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _due_days(db: Session) -> int:
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    features = (org.features if org else None) or {}
    try:
        return max(0, int(features.get("recurring_billing_due_days", DEFAULT_DUE_DAYS)))
    except (TypeError, ValueError):
        return DEFAULT_DUE_DAYS


def compute_period(frequency: str, today: date) -> tuple[date, date]:
    """Return the calendar period (start, end) containing ``today`` for ``frequency``.

    - monthly   → current calendar month
    - quarterly → current calendar quarter (Jan–Mar / Apr–Jun / Jul–Sep / Oct–Dec)
    - annual    → current calendar year

    Raises ``ValueError`` for any non-billable frequency (e.g. ``one_time``).
    """
    if frequency == "monthly":
        start = date(today.year, today.month, 1)
        end = date(today.year, today.month, _last_day_of_month(today.year, today.month))
    elif frequency == "quarterly":
        start_month = ((today.month - 1) // 3) * 3 + 1
        end_month = start_month + 2
        start = date(today.year, start_month, 1)
        end = date(today.year, end_month, _last_day_of_month(today.year, end_month))
    elif frequency == "annual":
        start = date(today.year, 1, 1)
        end = date(today.year, 12, 31)
    else:
        raise ValueError(f"Unsupported billing frequency: {frequency!r}")
    return start, end


def effective_billing_day(today: date, billing_day: int) -> int:
    """The configured billing day, pulled back to the last day of a short month.

    "Bill on the 31st" is a reasonable month-end choice, and 29/30/31 are all
    reachable through the settings API. Taken literally they make the scheduled
    task find nothing due in February (and, for 31, in four more months) — the
    month is skipped in silence. Clamping bills those months on their last day.
    """
    return min(max(billing_day, 1), _last_day_of_month(today.year, today.month))


def is_frequency_due(frequency: str, today: date, billing_day: int) -> bool:
    """Whether the scheduled task should bill ``frequency`` on ``today``.

    Gated on the single configured day-of-month, then on whether ``today`` falls in
    the first month of the frequency's period (quarterly → Jan/Apr/Jul/Oct, annual →
    January). Monthly is due every month on the configured day.
    """
    if today.day != effective_billing_day(today, billing_day):
        return False
    if frequency == "monthly":
        return True
    if frequency == "quarterly":
        return today.month in QUARTER_START_MONTHS
    if frequency == "annual":
        return today.month == 1
    return False


def run_billing(
    db: Session,
    frequency: str,
    triggered_by: str,
    user_id: int | None = None,
    today: date | None = None,
) -> BillingRun:
    """Generate membership fees for ``frequency``'s current period, logging a BillingRun.

    Receipts are emitted, not left ``pending``: nobody is at the keyboard to press
    "Emit" on an unattended run, and until a fee is emitted it is eligible for
    neither a SEPA remittance nor the overdue/reminder pipeline. They also carry a
    due date (``recurring_billing_due_days`` after emission, default 30) for the
    same reason — ``mark_overdue`` skips receipts that have none.

    Idempotent per period: if a successful run already exists for
    ``(frequency, period_start, period_end)`` it is returned unchanged and no
    receipts are generated. A previously failed run for the same period is retried
    in place (the underlying skip-if-exists logic avoids double-billing members who
    already got a receipt). Does not commit — the caller owns the transaction.
    """
    today = today or date.today()
    period_start, period_end = compute_period(frequency, today)
    due_date = today + timedelta(days=_due_days(db))

    existing = (
        db.query(BillingRun)
        .filter(
            BillingRun.frequency == frequency,
            BillingRun.period_start == period_start,
            BillingRun.period_end == period_end,
        )
        .first()
    )
    if existing is not None and existing.status == "success":
        return existing

    # Generate receipts first (it flushes internally), inside a SAVEPOINT so a
    # failure rolls back its own partial receipts and leaves the session usable to
    # record the failed run. Only build the BillingRun row afterwards, with a final
    # status — otherwise the internal flush would insert a status-less row.
    receipts_generated = 0
    errors: list[dict] = []
    try:
        with db.begin_nested():
            receipts = generate_membership_fees(
                db,
                GenerateMembershipFeesRequest(
                    billing_period_start=period_start,
                    billing_period_end=period_end,
                    emission_date=today,
                    due_date=due_date,
                ),
                created_by_id=user_id,
                billing_frequency=frequency,
                emit=True,
            )
            receipts_generated = len(receipts)
        status = "success"
    except Exception as exc:  # noqa: BLE001 — recorded on the run for the admin to retry
        receipts_generated = 0
        errors = [{"error": str(exc)}]
        status = "failed"

    run = existing or BillingRun(
        frequency=frequency,
        period_start=period_start,
        period_end=period_end,
    )
    run.triggered_by = triggered_by
    run.triggered_by_user_id = user_id
    run.receipts_generated = receipts_generated
    run.status = status
    run.errors = errors
    run.finished_at = func.now()
    if existing is None:
        db.add(run)
    db.flush()
    return run


def run_scheduled_billing(db: Session, today: date | None = None) -> list[BillingRun]:
    """Celery Beat entry point: bill every frequency that is due today.

    No-op (returns ``[]``) when recurring billing is disabled in org settings or when
    no frequency is due on the configured day. Does not commit.
    """
    today = today or date.today()
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    features = (org.features if org else None) or {}

    if not features.get("recurring_billing_enabled"):
        return []

    billing_day = features.get("recurring_billing_day", 1)

    runs: list[BillingRun] = []
    for frequency in BILLABLE_FREQUENCIES:
        if is_frequency_due(frequency, today, billing_day):
            runs.append(run_billing(db, frequency, "scheduled", today=today))
    return runs
