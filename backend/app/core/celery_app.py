"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery = Celery(
    "memship",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_BROKER_URL,
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

# Beat schedule — daily recurring-billing check at 02:00 UTC. The task itself is a
# no-op unless recurring billing is enabled and a frequency is due on the day.
celery.conf.beat_schedule = {
    "scheduled-billing-run": {
        "task": "app.tasks.billing_tasks.scheduled_billing_run",
        "schedule": crontab(hour=2, minute=0),
    },
}

# Auto-discover tasks in app.tasks package
celery.autodiscover_tasks(["app.tasks"])
