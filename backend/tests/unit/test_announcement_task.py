"""send_announcement_task's early exits and its retry (#358).

The fan-out itself is covered end to end in test_announcement_delivery_record;
these are the branches that return before it, and the exception path.
"""

from unittest.mock import MagicMock, patch

from app.tasks.communication_tasks import send_announcement_task


def _session(announcement):
    db = MagicMock(name="db")
    db.query.return_value.filter.return_value.first.return_value = announcement
    return db


def test_a_missing_announcement_sends_nothing_and_is_not_retried():
    db = _session(None)
    with patch("app.db.session.SessionLocal", return_value=db) as factory:
        result = send_announcement_task.apply(kwargs={"announcement_id": 404})
    assert result.get() == 0
    assert factory.call_count == 1
    db.close.assert_called_once()


def test_a_disabled_announcement_template_skips_the_audience_entirely():
    db = _session(MagicMock(name="announcement"))
    with patch("app.db.session.SessionLocal", return_value=db), patch(
        "app.domains.mailing.policy.is_enabled", return_value=False
    ), patch("app.domains.communications.service.resolve_audience") as resolve:
        result = send_announcement_task.apply(kwargs={"announcement_id": 1})
    assert result.get() == 0
    resolve.assert_not_called()
    db.close.assert_called_once()


def test_an_unreachable_database_is_retried_then_fails():
    with patch(
        "app.db.session.SessionLocal", side_effect=ConnectionError("database down")
    ) as factory:
        result = send_announcement_task.apply(kwargs={"announcement_id": 1})
    assert factory.call_count == send_announcement_task.max_retries + 1
    assert result.failed()
