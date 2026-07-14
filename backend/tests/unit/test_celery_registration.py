"""Regression tests for Celery task registration and worker mapper setup.

Guards against two bugs that let beat dispatch tasks the worker could not run:

1. ``autodiscover_tasks(["app.tasks"])`` looked for a non-existent
   ``app.tasks.tasks`` module, so the worker registered zero tasks and
   beat-dispatched tasks arrived unregistered
   (``KeyError: 'app.tasks.billing_tasks.scheduled_billing_run'``).

2. The worker does not import the full API, so the SQLAlchemy mapper registry
   was incomplete and string-based relationships (e.g. ``Receipt`` ->
   ``Registration``) failed to resolve at query time.
"""

from sqlalchemy.orm import configure_mappers

from app.core.celery_app import celery


def _boot_worker_task_registry():
    """Reproduce what a worker/beat process does at startup: import the
    modules listed in ``conf.include`` so their @celery.task functions register.
    """
    celery.loader.import_default_modules()
    return set(celery.tasks)


def test_every_beat_scheduled_task_is_registered():
    """Every task referenced by beat_schedule must be registered on the worker.

    Directly reproduces bug #1: with the old autodiscover call these names were
    absent, so beat dispatched tasks the worker rejected as unregistered.
    """
    registered = _boot_worker_task_registry()

    scheduled = {entry["task"] for entry in celery.conf.beat_schedule.values()}
    assert scheduled, "beat_schedule is empty — nothing to guard"

    missing = scheduled - registered
    assert not missing, f"beat-scheduled tasks not registered on worker: {sorted(missing)}"


def test_billing_tasks_registered():
    """Explicit guard for the exact task from the original incident."""
    registered = _boot_worker_task_registry()

    assert "app.tasks.billing_tasks.scheduled_billing_run" in registered
    assert "app.tasks.billing_tasks.scheduled_payment_reminders" in registered


def test_worker_mapper_registry_is_complete():
    """Importing the celery app must configure the full SQLAlchemy mapper
    registry (bug #2). configure_mappers() raises if any string-based
    relationship — e.g. Receipt -> Registration — cannot be resolved.
    """
    # Boot the worker task registry first: this loads billing_tasks -> the
    # billing service -> the Receipt model, whose relationship references
    # Registration by name. Importing app.core.celery_app pulls in
    # app.db.models_registry, which loads Registration (and every other model);
    # if that wiring regresses, configure_mappers() raises here.
    _boot_worker_task_registry()
    configure_mappers()
