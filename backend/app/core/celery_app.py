"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery = Celery(
    "memship",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_BROKER_URL,
    include=[
        "app.tasks.billing_tasks",
        "app.tasks.communication_tasks",
        "app.tasks.email_tasks",
    ],
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Beat schedule. Each task is a no-op unless its feature is enabled in org settings.
#  - recurring billing at 02:00 UTC (generates due membership fees)
#  - payment reminders at 03:00 UTC (after billing: mark overdue, send dunning)
celery.conf.beat_schedule = {
    "scheduled-billing-run": {
        "task": "app.tasks.billing_tasks.scheduled_billing_run",
        "schedule": crontab(hour=2, minute=0),
    },
    "scheduled-payment-reminders": {
        "task": "app.tasks.billing_tasks.scheduled_payment_reminders",
        "schedule": crontab(hour=3, minute=0),
    },
}

# Load every model so the SQLAlchemy mapper registry is fully configured in the
# worker/beat processes, which don't import the full API. Without this, string-based
# relationships (e.g. Receipt -> Registration) fail to resolve at query time.
import app.db.models_registry  # noqa: E402,F401
