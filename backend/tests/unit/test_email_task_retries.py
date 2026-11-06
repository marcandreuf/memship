"""The email tasks' bodies and their exception-driven retry (#358).

Elsewhere these tasks are only ever reached through a mocked ``.delay``, so
what a worker actually runs — delegate to the sender, retry when it raises,
give up after ``max_retries`` — was never executed. Run eagerly with
``.apply()``: Celery plays each retry in place, ignoring the countdown.
"""

from unittest.mock import patch

import pytest

from app.tasks import email_tasks
from app.tasks.email_tasks import (
    send_booking_email_task,
    send_cancellation_email_task,
    send_email_task,
    send_promotion_email_task,
    send_receipt_email_task,
    send_registration_email_task,
)

# (task, the sender it delegates to, kwargs). One row per task whose only
# behaviour is "send, and retry on an exception".
TASKS = [
    (
        send_email_task,
        "send_email",
        {"to": "ana@club.example", "subject": "Hola", "html_body": "<p>Hola</p>"},
    ),
    (
        send_registration_email_task,
        "send_registration_confirmation_email",
        {"to": "ana@club.example", "member_name": "Ana", "activity_name": "Yoga",
         "status": "confirmed"},
    ),
    (
        send_cancellation_email_task,
        "send_registration_cancellation_email",
        {"to": "ana@club.example", "member_name": "Ana", "activity_name": "Yoga"},
    ),
    (
        send_promotion_email_task,
        "send_waitlist_promotion_email",
        {"to": "ana@club.example", "member_name": "Ana", "activity_name": "Yoga"},
    ),
    (
        send_booking_email_task,
        "send_booking_confirmation_email",
        {"kind": "confirmation", "to": "ana@club.example", "member_name": "Ana",
         "space_name": "Pista 1", "date_str": "2026-11-06", "time_str": "18:00"},
    ),
]
IDS = [task.name.rsplit(".", 1)[-1] for task, _, _ in TASKS]


def _run(task, sender, kwargs, side_effect):
    with patch.object(email_tasks, sender, side_effect=side_effect) as send:
        result = task.apply(kwargs=kwargs)
    return result, send.call_count


@pytest.mark.parametrize("task,sender,kwargs", TASKS, ids=IDS)
def test_returns_what_the_sender_reports(task, sender, kwargs):
    result, attempts = _run(task, sender, kwargs, [True])
    assert result.get() is True
    assert attempts == 1


@pytest.mark.parametrize("task,sender,kwargs", TASKS, ids=IDS)
def test_a_raising_send_is_retried_until_it_goes_out(task, sender, kwargs):
    result, attempts = _run(task, sender, kwargs, [ConnectionError("smtp down"), True])
    assert result.get() is True
    assert attempts == 2


@pytest.mark.parametrize("task,sender,kwargs", TASKS, ids=IDS)
def test_gives_up_after_max_retries_and_fails(task, sender, kwargs):
    failures = [ConnectionError("smtp down")] * (task.max_retries + 1)
    result, attempts = _run(task, sender, kwargs, failures)
    # The first attempt plus one per retry, and then the error surfaces rather
    # than being swallowed into a False that reads like "nothing to send".
    assert attempts == task.max_retries + 1
    assert result.failed()
    assert isinstance(result.result, ConnectionError)


def test_receipt_email_retries_when_the_database_is_unreachable():
    calls = []

    def unreachable():
        calls.append(1)
        raise ConnectionError("database down")

    with patch("app.db.session.SessionLocal", side_effect=unreachable):
        result = send_receipt_email_task.apply(kwargs={"receipt_id": 1})
    assert len(calls) == send_receipt_email_task.max_retries + 1
    assert result.failed()


def test_receipt_email_for_a_missing_receipt_is_not_retried():
    with patch("app.db.session.SessionLocal") as session_factory:
        db = session_factory.return_value
        db.query.return_value.filter.return_value.first.return_value = None
        result = send_receipt_email_task.apply(kwargs={"receipt_id": 999})
    assert result.get() is False
    assert session_factory.call_count == 1
    db.close.assert_called_once()
