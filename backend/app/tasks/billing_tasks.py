"""Celery tasks for recurring (scheduled) membership billing and payment reminders."""

import logging

from sqlalchemy.orm import Session

from app.core.celery_app import celery

logger = logging.getLogger(__name__)


def _notify_admin(db, runs) -> None:
    """Send the optional post-run summary email if an address is configured.

    No-op when ``billing_notification_email`` is unset. Best-effort: a failure to
    send must not fail the billing run itself.
    """
    from app.core.email import send_billing_summary_email
    from app.domains.organizations.models import OrganizationSettings

    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    features = (org.features if org else None) or {}
    to = features.get("billing_notification_email")
    if not to:
        return

    total = sum(r.receipts_generated for r in runs)
    any_failed = any(r.status != "success" for r in runs)
    locale = (org.locale if org else None) or "es"
    rows = [
        {"frequency": r.frequency, "count": r.receipts_generated, "status": r.status}
        for r in runs
    ]

    try:
        send_billing_summary_email(to, rows, total, any_failed, locale)
    except Exception as exc:  # noqa: BLE001 — notification is best-effort
        logger.error(f"Billing notification email failed: to={to}, error={exc}")


@celery.task
def scheduled_billing_run() -> dict:
    """Daily Beat entry point: run any due recurring billing, then notify admin.

    Returns a small summary dict for the Celery result backend / logs.
    """
    from app.db.session import SessionLocal
    from app.domains.billing.recurring_billing_service import run_scheduled_billing

    db = SessionLocal()
    try:
        runs = run_scheduled_billing(db)
        db.commit()
        if runs:
            _notify_admin(db, runs)
        summary = {
            "runs": len(runs),
            "receipts_generated": sum(r.receipts_generated for r in runs),
        }
        logger.info(f"Scheduled billing run complete: {summary}")
        return summary
    except Exception as exc:
        db.rollback()
        logger.error(f"Scheduled billing run failed: {exc}")
        raise
    finally:
        db.close()


@celery.task
def scheduled_payment_reminders() -> dict:
    """Daily Beat entry point: void expired purchases, mark overdue, then remind.

    Abandoned plan purchases are voided first and unconditionally. They are not
    debts — nobody received the plan — so they must never reach ``mark_overdue``
    and be chased for money that is not owed, and that has to hold whether or
    not the club has switched payment reminders on. Everything after it is the
    ordinary dunning pass, which stays a no-op (zero counts) while reminders are
    disabled in org settings.

    Returns a small summary dict for the Celery result backend / logs.
    """
    from app.db.session import SessionLocal
    from app.domains.billing.membership_purchase_service import expire_unpaid_purchases
    from app.domains.billing.reminder_service import run_scheduled_reminders

    db = SessionLocal()
    try:
        purchases_expired = expire_unpaid_purchases(db)
        summary = {"purchases_expired": purchases_expired}
        summary.update(run_scheduled_reminders(db))
        db.commit()
        logger.info(f"Scheduled payment reminders complete: {summary}")
        return summary
    except Exception as exc:
        db.rollback()
        logger.error(f"Scheduled payment reminders failed: {exc}")
        raise
    finally:
        db.close()


@celery.task
def payment_notifications_fanout(receipt_ids: list[int]) -> int:
    """Queue one notification task per receipt that has just been paid.

    Enqueued once by ``dispatch_payment_notifications``, whatever the batch
    size: closing a SEPA remittance can settle hundreds of receipts, and the
    request that does it must not make hundreds of queue round-trips. Fanning
    out from a worker instead gives every receipt its own task, so one that
    fails — a bad address, a template error — cannot strand the rest.
    """
    for receipt_id in receipt_ids:
        send_payment_notification.delay(receipt_id)
    return len(receipt_ids)


def _send_payment_confirmation(db: Session, receipt_id: int) -> bool:
    """Compose and send the confirmation for one receipt that has been paid.

    Only what the receipt itself carries reaches the member: number, concept,
    amount, payment date and — when the method settles out of sight — how it was
    paid. Nothing about the mandate or the account it was collected from; a
    member does not expect their bank details in an inbox.
    """
    from app.core.email import send_payment_confirmation_email
    from app.domains.billing.models import Receipt
    from app.domains.billing.pdf import PAYMENT_METHOD_LABELS
    from app.domains.members.models import Member
    from app.domains.organizations.models import OrganizationSettings
    from app.domains.persons.models import Person

    receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
    if not receipt:
        logger.warning(f"Receipt {receipt_id} not found for payment notification")
        return False

    member = db.query(Member).filter(Member.id == receipt.member_id).first()
    person = (
        db.query(Person).filter(Person.id == member.person_id).first() if member else None
    )
    if not person or not person.email:
        logger.warning(f"No email for the payer of receipt {receipt_id}")
        return False

    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    locale = (org.locale if org else None) or "es"
    labels = PAYMENT_METHOD_LABELS.get(locale, PAYMENT_METHOD_LABELS["es"])

    return send_payment_confirmation_email(
        to=person.email,
        member_name=" ".join(filter(None, [person.first_name, person.last_name]))
        or person.email,
        receipt_number=receipt.receipt_number,
        description=receipt.description,
        amount=f"{receipt.total_amount:.2f}",
        currency=(org.currency if org else None) or "EUR",
        payment_date=receipt.payment_date.isoformat() if receipt.payment_date else "",
        org_name=(org.name if org else None) or "Memship",
        payment_method_label=labels.get(receipt.payment_method),
        locale=locale,
    )


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def send_payment_notification(self, receipt_id: int) -> bool:
    """Send the outbound notifications owed for one paid receipt.

    The seam for anything that must be *sent* after a payment, as opposed to
    written: those effects run inline in ``mark_receipt_paid``, inside the
    transaction that records the payment.

    Today that is the payment confirmation, which matters most for the methods
    that settle out of the member's sight — a SEPA collection reconciled days
    later, cash or a transfer marked paid by an admin. Off until the club
    switches it on, like every catalogued template.
    """
    from app.db.session import SessionLocal

    try:
        db = SessionLocal()
        try:
            return _send_payment_confirmation(db, receipt_id)
        finally:
            db.close()
    except Exception as exc:
        logger.error(
            f"Payment notification failed: receipt_id={receipt_id}, error={exc}"
        )
        raise self.retry(exc=exc)
