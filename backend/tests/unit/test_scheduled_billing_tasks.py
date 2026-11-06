"""The Beat entry points in billing_tasks, as a worker runs them (#358).

The services behind these tasks are tested on their own; what was never
executed is the task around them — the commit that makes a run stick, the
rollback and re-raise that keep a failed run from half-applying, the close
that returns the connection, and the best-effort notifications that must not
fail the run they report on. The session and the services are mocked so each
test is about exactly that wrapper.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from app.tasks import billing_tasks
from app.tasks.billing_tasks import (
    scheduled_billing_run,
    scheduled_membership_lapse,
    scheduled_payment_reminders,
    scheduled_webhook_digest,
    send_payment_notification,
    send_queued_reminder,
)


@pytest.fixture
def db():
    session = MagicMock(name="db")
    with patch("app.db.session.SessionLocal", return_value=session):
        yield session


def _org(db, **features):
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        features=features, locale="ca", timezone="Europe/Madrid"
    )


def _run(status="success", count=3, frequency="monthly"):
    return SimpleNamespace(status=status, receipts_generated=count, frequency=frequency)


# ---------------------------------------------------------------- billing run


def test_billing_run_commits_and_summarises(db):
    _org(db)
    with patch(
        "app.domains.billing.recurring_billing_service.run_scheduled_billing",
        return_value=[_run(count=3), _run(count=2, frequency="annual")],
    ):
        summary = scheduled_billing_run.apply().get()
    assert summary == {"runs": 2, "receipts_generated": 5}
    db.commit.assert_called_once()
    db.rollback.assert_not_called()
    db.close.assert_called_once()


def test_billing_run_notifies_the_configured_address(db):
    _org(db, billing_notification_email="tresorer@club.example")
    runs = [_run(count=3), _run(status="failed", count=0, frequency="annual")]
    with patch(
        "app.domains.billing.recurring_billing_service.run_scheduled_billing",
        return_value=runs,
    ), patch("app.core.email.send_billing_summary_email") as send:
        scheduled_billing_run.apply().get()
    send.assert_called_once_with(
        "tresorer@club.example",
        [
            {"frequency": "monthly", "count": 3, "status": "success"},
            {"frequency": "annual", "count": 0, "status": "failed"},
        ],
        3,
        True,
        "ca",
    )


def test_billing_run_with_nothing_due_sends_nothing(db):
    _org(db, billing_notification_email="tresorer@club.example")
    with patch(
        "app.domains.billing.recurring_billing_service.run_scheduled_billing",
        return_value=[],
    ), patch("app.core.email.send_billing_summary_email") as send:
        summary = scheduled_billing_run.apply().get()
    assert summary == {"runs": 0, "receipts_generated": 0}
    send.assert_not_called()


def test_a_failed_summary_email_does_not_fail_the_run(db):
    _org(db, billing_notification_email="tresorer@club.example")
    with patch(
        "app.domains.billing.recurring_billing_service.run_scheduled_billing",
        return_value=[_run()],
    ), patch("app.core.email.send_billing_summary_email", side_effect=OSError("smtp down")):
        result = scheduled_billing_run.apply()
    assert result.successful()
    db.commit.assert_called_once()


def test_a_failed_billing_run_rolls_back_and_raises(db):
    with patch(
        "app.domains.billing.recurring_billing_service.run_scheduled_billing",
        side_effect=RuntimeError("numbering conflict"),
    ):
        result = scheduled_billing_run.apply()
    assert result.failed()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()
    db.close.assert_called_once()


# ---------------------------------------------------------------- reminders


def test_reminders_void_expired_purchases_before_chasing_anyone(db):
    order = MagicMock()
    order.expire.return_value = 2
    order.remind.return_value = {"marked_overdue": 4, "reminders_sent": 3}
    with patch(
        "app.domains.billing.membership_purchase_service.expire_unpaid_purchases",
        order.expire,
    ), patch("app.domains.billing.reminder_service.run_scheduled_reminders", order.remind):
        summary = scheduled_payment_reminders.apply().get()
    # An abandoned purchase is not a debt: it must be voided before the pass
    # that marks receipts overdue could see it.
    assert order.mock_calls[:2] == [call.expire(db), call.remind(db)]
    assert summary == {"purchases_expired": 2, "marked_overdue": 4, "reminders_sent": 3}
    db.commit.assert_called_once()
    db.close.assert_called_once()


def test_a_failed_reminder_pass_rolls_back_the_voided_purchases_too(db):
    with patch(
        "app.domains.billing.membership_purchase_service.expire_unpaid_purchases",
        return_value=2,
    ), patch(
        "app.domains.billing.reminder_service.run_scheduled_reminders",
        side_effect=RuntimeError("mail transport misconfigured"),
    ):
        result = scheduled_payment_reminders.apply()
    assert result.failed()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()
    db.close.assert_called_once()


# ---------------------------------------------------------------- lapse


def test_lapse_commits_and_returns_the_service_summary(db):
    with patch(
        "app.domains.billing.lapse_service.revert_lapsed_members",
        return_value={"reverted": 1},
    ):
        summary = scheduled_membership_lapse.apply().get()
    assert summary == {"reverted": 1}
    db.commit.assert_called_once()
    db.close.assert_called_once()


def test_a_failed_lapse_run_rolls_back_and_raises(db):
    with patch(
        "app.domains.billing.lapse_service.revert_lapsed_members",
        side_effect=RuntimeError("boom"),
    ):
        result = scheduled_membership_lapse.apply()
    assert result.failed()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()
    db.close.assert_called_once()


# ---------------------------------------------------------------- digest


def test_a_failed_digest_email_is_reported_not_raised(db):
    _org(db, billing_notification_email="tresorer@club.example")
    digest = SimpleNamespace(is_empty=False, events=[], events_total=2, rejections=[{}])
    with patch("app.domains.billing.webhook_digest.build_digest", return_value=digest), patch(
        "app.core.email.send_webhook_digest_email", side_effect=OSError("smtp down")
    ):
        summary = scheduled_webhook_digest.apply().get()
    assert summary == {"sent": False, "events": 2, "rejections": 1}
    db.close.assert_called_once()


# ---------------------------------------------------------------- payment notification


def test_payment_notification_sends_through_a_fresh_session(db):
    with patch.object(billing_tasks, "_send_payment_confirmation", return_value=True) as send:
        assert send_payment_notification.apply(kwargs={"receipt_id": 7}).get() is True
    send.assert_called_once_with(db, 7)
    db.close.assert_called_once()


def test_payment_notification_retries_then_gives_up(db):
    failures = [ConnectionError("smtp down")] * (send_payment_notification.max_retries + 1)
    with patch.object(billing_tasks, "_send_payment_confirmation", side_effect=failures) as send:
        result = send_payment_notification.apply(kwargs={"receipt_id": 7})
    assert send.call_count == send_payment_notification.max_retries + 1
    assert result.failed()
    # Every attempt opened its own session and returned it.
    assert db.close.call_count == send.call_count


# ---------------------------------------------------------------- queued reminder


def test_a_queued_reminder_that_fails_to_record_rolls_back_and_raises(db):
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        status="queued"
    )
    with patch(
        "app.domains.billing.reminder_service.deliver", side_effect=RuntimeError("boom")
    ):
        result = send_queued_reminder.apply(kwargs={"reminder_id": 5, "payload": {}})
    assert result.failed()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()
    db.close.assert_called_once()
