"""Scheduled auth maintenance."""

import logging

from app.core.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(name="app.tasks.auth_tasks.scheduled_unverified_cleanup")
def scheduled_unverified_cleanup() -> dict:
    """Daily Beat entry point: delete accounts nobody ever confirmed.

    Hygiene rather than a fix. #644 frees an address the moment somebody with a
    better claim arrives; this clears the ones nobody comes back for.

    Returns a small summary dict for the Celery result backend / logs.
    """
    from app.db.session import SessionLocal
    from app.domains.auth.cleanup_service import purge_unverified_accounts

    db = SessionLocal()
    try:
        summary = purge_unverified_accounts(db)
        db.commit()
        logger.info(f"Unverified account cleanup complete: {summary}")
        return summary
    except Exception as exc:
        db.rollback()
        logger.error(f"Unverified account cleanup failed: {exc}")
        raise
    finally:
        db.close()
