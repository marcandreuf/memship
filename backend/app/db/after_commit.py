"""Defer a side effect until the session's transaction actually commits.

Queueing an email from inside a service function is a race: the Celery worker
can pick the task up before the row it describes is visible, and if the
endpoint's ``db.commit()`` then fails the member has already been told about a
registration that does not exist. ``run_after_commit`` parks the callable on
the session and runs it from the ``after_commit`` event, so it fires only once
the data is durable. A rollback drops the queue without running anything.

Callables must not touch the session — by the time they run, ``commit()`` has
expired every loaded instance, so resolve the payload first and close over
plain values.
"""

import logging
from collections.abc import Callable

from sqlalchemy import event
from sqlalchemy.orm import Session, SessionTransaction

logger = logging.getLogger(__name__)

_QUEUE_KEY = "after_commit_hooks"


def run_after_commit(db: Session, fn: Callable[[], None]) -> None:
    """Run ``fn`` after the next successful commit on ``db``; drop it on rollback."""
    queue = db.info.get(_QUEUE_KEY)
    if queue is None:
        queue = db.info[_QUEUE_KEY] = []
        event.listen(db, "after_commit", _run_queued)
        event.listen(db, "after_soft_rollback", _discard_queued)
    queue.append(fn)


def _run_queued(session: Session) -> None:
    queue = session.info.get(_QUEUE_KEY) or []
    session.info[_QUEUE_KEY] = []
    for fn in queue:
        try:
            fn()
        except Exception:  # noqa: BLE001 — a failed side effect must not undo a commit
            logger.exception("after-commit hook failed")


def _discard_queued(session: Session, previous_transaction: SessionTransaction) -> None:
    # ``after_soft_rollback`` also fires when a SAVEPOINT from ``begin_nested()``
    # is rolled back. That undoes only the nested work, so hooks queued by the
    # enclosing transaction — which may still commit — must survive it.
    if previous_transaction.nested:
        return
    session.info[_QUEUE_KEY] = []
