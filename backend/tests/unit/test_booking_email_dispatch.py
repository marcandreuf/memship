"""Every branch of ``send_booking_email_task`` must match its sender.

The task fans four booking mails out to four senders, passing their arguments
positionally. A sender that grows or loses a parameter without the call site
following raises ``TypeError`` inside the task, which Celery turns into three
silent retries and a lost mail — the member is never told (#227). Nothing else
covers the enabled path, so the mismatch survived review.

These tests call the task body for each kind and let the real senders run, so a
future signature change fails here rather than in a worker log.
"""

from unittest.mock import patch

import pytest

from app.tasks.email_tasks import send_booking_email_task

KINDS = ["confirmation", "waitlisted", "promoted", "cancelled"]

DISPATCH_ARGS = {
    "to": "member@example.com",
    "member_name": "Alex",
    "space_name": "Court 1",
    "date_str": "24/07/2026",
    "time_str": "10:00–11:00",
    "locale": "es",
    "position": 3,
    "cancellation_deadline_hours": 24,
}


@pytest.fixture
def sent():
    """Capture what reaches the transport, with the settings gate held open."""
    captured = []

    def _capture(to, subject, html_body):
        captured.append({"to": to, "subject": subject, "html": html_body})
        return True

    with (
        patch("app.core.email._template_enabled", return_value=True),
        patch("app.core.email.send_email", side_effect=_capture),
    ):
        yield captured


@pytest.mark.parametrize("kind", KINDS)
def test_every_kind_reaches_the_transport(kind, sent):
    """The full dispatch payload binds to every sender, positionally."""
    assert send_booking_email_task(kind=kind, **DISPATCH_ARGS) is True
    assert len(sent) == 1
    assert sent[0]["to"] == DISPATCH_ARGS["to"]
    assert "Court 1" in sent[0]["html"]


def test_waitlisted_mail_carries_the_queue_position(sent):
    """``position`` reaches the template — the row it renders was dead before."""
    send_booking_email_task(kind="waitlisted", **{**DISPATCH_ARGS, "position": 3})
    assert "3" in sent[0]["html"]
    assert "posición" in sent[0]["html"].lower()


def test_waitlisted_mail_without_a_position_still_sends(sent):
    """``position`` is optional; the template's row is conditional on it."""
    args = {**DISPATCH_ARGS, "position": None}
    assert send_booking_email_task(kind="waitlisted", **args) is True
    assert "posición" not in sent[0]["html"].lower()


def test_unknown_kind_is_refused_without_mailing(sent):
    assert send_booking_email_task(kind="nonsense", **DISPATCH_ARGS) is False
    assert sent == []
