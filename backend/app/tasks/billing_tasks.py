"""Celery tasks for recurring (scheduled) membership billing and payment reminders."""

import logging

from app.core.celery_app import celery

logger = logging.getLogger(__name__)


def _notify_admin(db, runs) -> None:
    """Send the optional post-run summary email if an address is configured.

    No-op when ``billing_notification_email`` is unset. Best-effort: a failure to
    send must not fail the billing run itself.
    """
    from app.core.email import send_email
    from app.domains.organizations.models import OrganizationSettings

    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    features = (org.features if org else None) or {}
    to = features.get("billing_notification_email")
    if not to:
        return

    total = sum(r.receipts_generated for r in runs)
    any_failed = any(r.status != "success" for r in runs)
    locale = (org.locale if org else None) or "es"

    subjects = {
        "es": f"Facturación recurrente — {total} recibos generados",
        "ca": f"Facturació recurrent — {total} rebuts generats",
        "en": f"Recurring billing — {total} receipts generated",
    }
    lines = "".join(
        f"<li>{r.frequency}: {r.receipts_generated} ({r.status})</li>" for r in runs
    )
    intro = {
        "es": "<p>Resumen de la facturación recurrente:</p>",
        "ca": "<p>Resum de la facturació recurrent:</p>",
        "en": "<p>Recurring billing summary:</p>",
    }
    html_body = f"{intro.get(locale, intro['es'])}<ul>{lines}</ul>"
    if any_failed:
        warn = {
            "es": "<p><strong>Algunas ejecuciones fallaron — revisa el historial.</strong></p>",
            "ca": "<p><strong>Algunes execucions han fallat — revisa l'historial.</strong></p>",
            "en": "<p><strong>Some runs failed — check the run history.</strong></p>",
        }
        html_body += warn.get(locale, warn["es"])

    try:
        send_email(to, subjects.get(locale, subjects["es"]), html_body)
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
    """Daily Beat entry point: mark overdue receipts, then send due reminders.

    No-op (returns zero counts) unless payment reminders are enabled in org
    settings. Returns a small summary dict for the Celery result backend / logs.
    """
    from app.db.session import SessionLocal
    from app.domains.billing.reminder_service import run_scheduled_reminders

    db = SessionLocal()
    try:
        summary = run_scheduled_reminders(db)
        db.commit()
        logger.info(f"Scheduled payment reminders complete: {summary}")
        return summary
    except Exception as exc:
        db.rollback()
        logger.error(f"Scheduled payment reminders failed: {exc}")
        raise
    finally:
        db.close()
