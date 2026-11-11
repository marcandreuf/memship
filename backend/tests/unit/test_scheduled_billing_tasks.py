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
    assert summary == {"runs": 2, "receipts_generated": 5, "receipts_emailed": 0}
    db.commit.assert_called_once()
    db.rollback.assert_not_called()
    db.close.assert_called_once()


def _emits(*receipt_ids, count=None):
    """Stand in for run_scheduled_billing, filling the out-parameter as it does."""

    def _run_it(db, today=None, emitted_receipt_ids=None):
        if emitted_receipt_ids is not None:
            emitted_receipt_ids.extend(receipt_ids)
        return [_run(count=count if count is not None else len(receipt_ids))]

    return _run_it


def test_the_run_emails_every_receipt_it_emitted(db):
    """The gap #580 reported: the run raised the fees and told nobody."""
    _org(db)
    with patch(
        "app.domains.billing.recurring_billing_service.run_scheduled_billing",
        side_effect=_emits(11, 12, 13),
    ), patch("app.tasks.billing_tasks.receipt_deliveries_fanout") as fanout:
        summary = scheduled_billing_run.apply().get()
    # One fan-out job carrying every id, not one queue round-trip per receipt:
    # a monthly run bills every active member.
    fanout.delay.assert_called_once_with([11, 12, 13])
    assert summary["receipts_emailed"] == 3


def test_the_receipts_are_queued_only_after_the_commit(db):
    """A worker must not read a receipt whose row is not visible yet."""
    _org(db)
    order = []
    db.commit.side_effect = lambda: order.append("commit")
    with patch(
        "app.domains.billing.recurring_billing_service.run_scheduled_billing",
        side_effect=_emits(21),
    ), patch(
        "app.domains.billing.service.dispatch_receipt_deliveries",
        side_effect=lambda ids: order.append("dispatch"),
    ):
        scheduled_billing_run.apply().get()
    assert order == ["commit", "dispatch"]


def test_a_broker_that_is_down_does_not_fail_the_run(db):
    """The receipts are recorded and valid; the mail is best-effort."""
    _org(db)
    with patch(
        "app.domains.billing.recurring_billing_service.run_scheduled_billing",
        side_effect=_emits(31),
    ), patch(
        "app.tasks.billing_tasks.receipt_deliveries_fanout"
    ) as fanout:
        fanout.delay.side_effect = OSError("broker down")
        result = scheduled_billing_run.apply()
    assert result.successful()
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_a_run_that_emitted_nothing_queues_nothing(db):
    """A retried period re-emits no receipts, so it must re-email nobody."""
    _org(db)
    with patch(
        "app.domains.billing.recurring_billing_service.run_scheduled_billing",
        side_effect=_emits(count=0),
    ), patch("app.tasks.billing_tasks.receipt_deliveries_fanout") as fanout:
        summary = scheduled_billing_run.apply().get()
    fanout.delay.assert_not_called()
    assert summary["receipts_emailed"] == 0


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
    assert summary == {"runs": 0, "receipts_generated": 0, "receipts_emailed": 0}
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


def test_reminders_void_what_was_abandoned_before_chasing_anyone(db):
    order = MagicMock()
    order.expire.return_value = 2
    order.expire_donations.return_value = 1
    order.remind.return_value = {"marked_overdue": 4, "reminders_sent": 3}
    with patch(
        "app.domains.billing.membership_purchase_service.expire_unpaid_purchases",
        order.expire,
    ), patch(
        "app.domains.billing.donation_service.expire_unpaid_donations",
        order.expire_donations,
    ), patch("app.domains.billing.reminder_service.run_scheduled_reminders", order.remind):
        summary = scheduled_payment_reminders.apply().get()
    # Neither an abandoned purchase nor an abandoned donation is a debt: both
    # must be voided before the pass that marks receipts overdue could see
    # them.
    assert order.mock_calls[:3] == [
        call.expire(db),
        call.expire_donations(db),
        call.remind(db),
    ]
    assert summary == {
        "purchases_expired": 2,
        "donations_expired": 1,
        "marked_overdue": 4,
        "reminders_sent": 3,
    }
    db.commit.assert_called_once()
    db.close.assert_called_once()


def test_a_failed_reminder_pass_rolls_back_the_voided_purchases_too(db):
    with patch(
        "app.domains.billing.membership_purchase_service.expire_unpaid_purchases",
        return_value=2,
    ), patch(
        "app.domains.billing.donation_service.expire_unpaid_donations",
        return_value=1,
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
