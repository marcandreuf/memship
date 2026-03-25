"""Celery application configuration."""

from celery import Celery

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

# Auto-discover tasks in app.tasks package
celery.autodiscover_tasks(["app.tasks"])
