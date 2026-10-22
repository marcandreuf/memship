"""Later attempts at a registration decision mail whose inline send failed (#449).

Run eagerly with ``.apply()``: Celery then executes each retry in place,
ignoring the countdown, so a whole schedule plays out inside one test.
"""

from unittest.mock import MagicMock, patch

from app.core.email import EmailFailure, EmailOutcome, EmailResult
from app.tasks import email_tasks
from app.tasks.email_tasks import (
    RETRY_DELAYS,
    queue_email_retry,
    retry_registration_approved_email_task,
    retry_registration_rejected_email_task,
)

SENT = EmailResult(EmailOutcome.SENT)
UNREACHABLE = EmailResult(EmailOutcome.FAILED, EmailFailure.TRANSPORT_UNAVAILABLE)
RATE_LIMITED = EmailResult(EmailOutcome.FAILED, EmailFailure.RATE_LIMITED)
REFUSED = EmailResult(EmailOutcome.FAILED, EmailFailure.INVALID_CREDENTIALS)

APPROVAL = {
    "to": "ana@club.example",
    "first_name": "Ana",
    "member_number": "M-0001",
    "login_url": "http://localhost:3000/es/login",
    "sso_providers": [],
    "has_password": True,
}


def _approve(*results):
    with patch.object(
        email_tasks, "send_registration_approved_email", side_effect=list(results)
    ) as send:
        outcome = retry_registration_approved_email_task.apply(kwargs=APPROVAL).get(
            propagate=False
        )
    return outcome, send.call_count


def test_a_transient_failure_is_tried_again_until_it_goes_out():
    outcome, attempts = _approve(UNREACHABLE, RATE_LIMITED, SENT)
    assert outcome is True
    assert attempts == 3


def test_the_schedule_ends_after_its_last_attempt():
    outcome, attempts = _approve(*[UNREACHABLE] * len(RETRY_DELAYS))
    # The inline send was attempt zero; the task makes one per remaining delay.
    assert attempts == len(RETRY_DELAYS)
    assert outcome is False


def test_a_permanent_failure_is_not_retried():
    outcome, attempts = _approve(REFUSED)
    assert outcome is False
    assert attempts == 1


def test_rejection_mail_retries_the_same_way():
    with patch.object(
        email_tasks, "send_registration_rejected_email", side_effect=[UNREACHABLE, SENT]
    ) as send:
        outcome = retry_registration_rejected_email_task.apply(
            kwargs={"to": "ana@club.example", "first_name": "Ana", "reason": "Full"}
        ).get()
    assert outcome is True
    assert send.call_count == 2


def test_queueing_waits_for_the_first_delay():
    task = MagicMock()
    assert queue_email_retry(task, to="ana@club.example") is True
    task.apply_async.assert_called_once_with(
        kwargs={"to": "ana@club.example"}, countdown=RETRY_DELAYS[0]
    )


def test_a_broker_that_is_down_reports_nothing_queued():
    task = MagicMock()
    task.apply_async.side_effect = ConnectionError("broker down")
    assert queue_email_retry(task, to="ana@club.example") is False
