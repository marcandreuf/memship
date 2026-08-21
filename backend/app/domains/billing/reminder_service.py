"""Payment reminder service — overdue transition, dunning schedule, sending.

Three concerns, mirroring ``recurring_billing_service``:

- ``mark_overdue`` flips unpaid ``pending``/``emitted`` receipts past their
  ``due_date`` to ``overdue`` so the rest of the app (stats, remittances) sees
  accurate status.
- ``reminders_due`` applies the configured schedule (first reminder X days after
  due, repeat every Y days, max N) to decide which overdue receipts need a
  reminder today.
- ``send_reminder`` renders + sends the email and logs a ``ReceiptReminder`` row.

Email-only for now. Does not commit — the caller owns the transaction.
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.email import send_payment_reminder_email
from app.domains.billing.models import PaymentProvider, Receipt, ReceiptReminder
from app.domains.members.models import Member
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person

# Receipt statuses that still owe money and can be reminded.
PAYABLE_STATUSES = ("emitted", "overdue")

# Statuses ``mark_overdue`` transitions once the due date has passed.
OVERDUE_ELIGIBLE_STATUSES = ("pending", "emitted")


def mark_overdue(db: Session, today: date | None = None) -> int:
    """Flip unpaid receipts whose ``due_date`` has passed to ``overdue``.

    Covers ``pending`` as well as ``emitted``. A ``pending`` receipt past its due
    date is money owed just the same — that is the status ``create_receipt`` and
    the manual fee generator produce — and ``VALID_TRANSITIONS`` already sanctions
    ``pending → overdue``. Filtering on ``emitted`` alone left those receipts out
    of the whole dunning pipeline, since ``reminders_due`` only looks at
    ``overdue``.

    Returns the number of receipts transitioned. Does not commit.
    """
    today = today or date.today()
    rows = (
        db.query(Receipt)
        .filter(
            Receipt.status.in_(OVERDUE_ELIGIBLE_STATUSES),
            Receipt.is_active.is_(True),
            Receipt.payment_date.is_(None),
            Receipt.due_date.isnot(None),
            Receipt.due_date < today,
        )
        .all()
    )
    for r in rows:
        r.status = "overdue"
    db.flush()
    return len(rows)


def _sent_reminders(receipt: Receipt) -> list[ReceiptReminder]:
    return [rem for rem in receipt.reminders if rem.status == "sent"]


def reminders_due(
    db: Session,
    today: date,
    days_after_due: int,
    repeat_days: int,
    max_count: int,
) -> list[Receipt]:
    """Overdue receipts that should receive a reminder ``today``.

    First reminder fires once ``today >= due_date + days_after_due``; each
    subsequent one once ``today >= last_sent + repeat_days``; never past
    ``max_count`` sent reminders, and never more than one per receipt per day.
    """
    candidates = (
        db.query(Receipt)
        .filter(
            Receipt.status == "overdue",
            Receipt.is_active.is_(True),
            Receipt.payment_date.is_(None),
            Receipt.due_date.isnot(None),
        )
        .all()
    )

    due: list[Receipt] = []
    for r in candidates:
        sent = _sent_reminders(r)
        if len(sent) >= max_count:
            continue
        last_sent_at = max((rem.sent_at for rem in sent), default=None)
        # One reminder per receipt per day (guards duplicate Beat firings and
        # manual + scheduled landing on the same day).
        if last_sent_at is not None and last_sent_at.date() == today:
            continue
        if not sent:
            if today >= r.due_date + timedelta(days=days_after_due):
                due.append(r)
        elif last_sent_at is not None and today >= last_sent_at.date() + timedelta(days=repeat_days):
            due.append(r)
    return due


def _has_active_online_provider(db: Session) -> bool:
    return (
        db.query(PaymentProvider)
        .filter(PaymentProvider.status.in_(["active", "test"]))
        .first()
        is not None
    )


def _recipient(db: Session, receipt: Receipt) -> tuple[Person | None, OrganizationSettings | None]:
    member = db.query(Member).filter(Member.id == receipt.member_id).first()
    person = (
        db.query(Person).filter(Person.id == member.person_id).first() if member else None
    )
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    return person, org


def send_reminder(
    db: Session,
    receipt: Receipt,
    triggered_by: str,
    user_id: int | None = None,
    today: date | None = None,
) -> ReceiptReminder:
    """Render and send a payment reminder for ``receipt``, logging a row.

    Raises ``ValueError`` if the member has no email (a precondition the manual
    endpoint surfaces to the admin). Send-transport failures are recorded as a
    ``failed`` row rather than raised. Does not commit.
    """
    today = today or date.today()
    person, org = _recipient(db, receipt)
    if person is None or not person.email:
        raise ValueError("Member has no email address")

    locale = (org.locale if org else None) or "es"
    currency = (org.currency if org else None) or "EUR"
    org_name = (org.name if org else None) or "Memship"
    member_name = " ".join(filter(None, [person.first_name, person.last_name])) or person.email
    days_overdue = max(0, (today - receipt.due_date).days) if receipt.due_date else 0

    pay_now_url = None
    bank_details = None
    if _has_active_online_provider(db):
        # The member's own page, not /receipts — that one is the admin list,
        # gated on `billing.read`, so the portal layout bounced the recipient of
        # every reminder we sent straight to /dashboard. See
        # frontend/lib/route-permissions.ts: /my-receipts wants
        # `self.billing.read`, which is what a member actually holds.
        pay_now_url = f"{settings.FRONTEND_URL}/{locale}/my-receipts"
    elif org and org.bank_iban:
        bank_details = " — ".join(filter(None, [org.bank_name, org.bank_iban]))

    reminder_number = len(_sent_reminders(receipt)) + 1

    sent_ok = False
    error = None
    try:
        sent_ok = send_payment_reminder_email(
            to=person.email,
            member_name=member_name,
            receipt_number=receipt.receipt_number,
            amount=f"{receipt.total_amount:.2f}",
            currency=currency,
            due_date=receipt.due_date.isoformat() if receipt.due_date else "",
            days_overdue=days_overdue,
            org_name=org_name,
            pay_now_url=pay_now_url,
            bank_details=bank_details,
            locale=locale,
        )
    except Exception as exc:  # noqa: BLE001 — recorded on the row for the admin
        error = str(exc)

    reminder = ReceiptReminder(
        receipt_id=receipt.id,
        reminder_number=reminder_number,
        channel="email",
        status="sent" if sent_ok else "failed",
        to_email=person.email,
        triggered_by=triggered_by,
        triggered_by_user_id=user_id,
        error=error if error else (None if sent_ok else "Email transport unavailable or send failed"),
    )
    db.add(reminder)
    db.flush()
    return reminder


def run_scheduled_reminders(db: Session, today: date | None = None) -> dict:
    """Celery Beat entry point: mark overdue, then send any due reminders.

    No-op (beyond the overdue transition being skipped too) when reminders are
    disabled in org settings. Does not commit.
    """
    today = today or date.today()
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    features = (org.features if org else None) or {}

    if not features.get("payment_reminders_enabled"):
        return {"overdue_marked": 0, "reminders_sent": 0, "failures": 0}

    days_after_due = features.get("reminder_days_after_due", 3)
    repeat_days = features.get("reminder_repeat_days", 7)
    max_count = features.get("reminder_max_count", 3)

    overdue_marked = mark_overdue(db, today)

    sent = 0
    failures = 0
    for receipt in reminders_due(db, today, days_after_due, repeat_days, max_count):
        try:
            reminder = send_reminder(db, receipt, "scheduled", today=today)
            if reminder.status == "sent":
                sent += 1
            else:
                failures += 1
        except ValueError:
            # No email — skip silently in the scheduled path.
            failures += 1

    return {
        "overdue_marked": overdue_marked,
        "reminders_sent": sent,
        "failures": failures,
    }
