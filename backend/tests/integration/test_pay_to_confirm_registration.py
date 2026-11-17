"""Registering for a pay-to-confirm activity holds the seat as pending (#591).

A ``legacy`` activity is checked alongside, because the promise to clubs with
activities already running is that nothing about them changes.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import func

from app.core.clock import org_timezone, org_today
from app.core.email import render_template
from app.domains.activities.models import ActivityPrice, Registration
from app.domains.activities.registration_service import (
    OCCUPYING_STATUSES,
    admin_change_status,
    cancel_registration,
    register_member,
)
from app.domains.activities.service import publish_activity
from tests.integration.test_registration_billing import (
    PRICE,
    _activity,
    _member,
    _receipts_for,
    membership_type,  # noqa: F401 — fixture
    org,  # noqa: F401 — fixture
)

PAY = "pay_to_confirm"


def _auto_cancel(org, *, enabled=True, hours=48):
    org.features = {
        **(org.features or {}),
        "activity_auto_cancel_enabled": enabled,
        "activity_auto_cancel_hours": hours,
    }


def _assert_counters_match_rows(db, activity):
    db.flush()
    db.refresh(activity)
    rows = dict(
        db.query(Registration.status, func.count())
        .filter(Registration.activity_id == activity.id)
        .group_by(Registration.status)
        .all()
    )
    occupying = sum(rows.get(s, 0) for s in OCCUPYING_STATUSES)
    assert activity.current_participants == occupying
    assert activity.waitlist_count == rows.get("waitlist", 0)
    for price in db.query(ActivityPrice).filter(ActivityPrice.activity_id == activity.id):
        db.refresh(price)
        held = (
            db.query(func.count())
            .select_from(Registration)
            .filter(
                Registration.price_id == price.id,
                Registration.status.in_(OCCUPYING_STATUSES),
            )
            .scalar()
        )
        assert price.current_registrations == held


class TestAPaidSeatIsPending:
    def test_the_registration_waits_for_payment(self, db, org, membership_type):
        activity, price = _activity(db, payment_flow=PAY)

        registration = register_member(
            db, activity, _member(db, membership_type, "p1"), price.id
        )

        assert registration.status == "pending"

    def test_its_receipt_is_raised_now_never_batchable_and_due(
        self, db, org, membership_type
    ):
        activity, price = _activity(db, payment_flow=PAY)

        registration = register_member(
            db, activity, _member(db, membership_type, "p2"), price.id
        )

        [receipt] = _receipts_for(db, registration)
        assert receipt.status == "emitted"
        assert receipt.base_amount == PRICE
        assert receipt.is_batchable is False
        assert receipt.due_date == org_today(db) + timedelta(days=7)

    def test_without_auto_cancel_there_is_no_deadline(self, db, org, membership_type):
        activity, price = _activity(db, payment_flow=PAY)

        registration = register_member(
            db, activity, _member(db, membership_type, "p3"), price.id
        )

        assert registration.payment_due_at is None

    def test_a_free_price_is_confirmed_at_once_with_no_receipt(
        self, db, org, membership_type
    ):
        activity, price = _activity(db, payment_flow=PAY, amount=Decimal("0"))

        registration = register_member(
            db, activity, _member(db, membership_type, "p4"), price.id
        )

        assert registration.status == "confirmed"
        assert _receipts_for(db, registration) == []


class TestTheDeadline:
    def test_the_club_default_sets_it(self, db, org, membership_type):
        _auto_cancel(org, hours=48)
        activity, price = _activity(db, payment_flow=PAY)
        before = datetime.now(timezone.utc)

        registration = register_member(
            db, activity, _member(db, membership_type, "d1"), price.id
        )

        due = registration.payment_due_at
        assert before + timedelta(hours=48) <= due <= datetime.now(timezone.utc) + timedelta(hours=48)
        [receipt] = _receipts_for(db, registration)
        assert receipt.due_date == due.astimezone(org_timezone(db)).date()

    def test_the_activity_can_shorten_it(self, db, org, membership_type):
        _auto_cancel(org, hours=48)
        activity, price = _activity(db, payment_flow=PAY)
        activity.auto_cancel_hours = 2
        before = datetime.now(timezone.utc)

        registration = register_member(
            db, activity, _member(db, membership_type, "d2"), price.id
        )

        assert registration.payment_due_at < before + timedelta(hours=3)

    def test_the_activity_can_switch_it_off(self, db, org, membership_type):
        _auto_cancel(org)
        activity, price = _activity(db, payment_flow=PAY)
        activity.auto_cancel_enabled = False

        registration = register_member(
            db, activity, _member(db, membership_type, "d3"), price.id
        )

        assert registration.payment_due_at is None

    def test_the_activity_can_switch_it_on(self, db, org, membership_type):
        _auto_cancel(org, enabled=False, hours=24)
        activity, price = _activity(db, payment_flow=PAY)
        activity.auto_cancel_enabled = True

        registration = register_member(
            db, activity, _member(db, membership_type, "d4"), price.id
        )

        assert registration.payment_due_at is not None


class TestAPendingSeatIsHeld:
    def test_the_next_member_goes_to_the_waiting_list(self, db, org, membership_type):
        activity, price = _activity(db, payment_flow=PAY, max_participants=1)

        first = register_member(db, activity, _member(db, membership_type, "h1"), price.id)
        second = register_member(db, activity, _member(db, membership_type, "h2"), price.id)

        assert (first.status, second.status) == ("pending", "waitlist")

    def test_cancelling_a_pending_seat_frees_it_and_voids_its_receipt(
        self, db, org, membership_type
    ):
        activity, price = _activity(db, payment_flow=PAY, max_participants=1)
        first = register_member(db, activity, _member(db, membership_type, "h3"), price.id)
        second = register_member(db, activity, _member(db, membership_type, "h4"), price.id)

        cancel_registration(db, first)

        assert second.status != "waitlist"
        assert _receipts_for(db, first)[0].status == "cancelled"
        _assert_counters_match_rows(db, activity)


class TestCountersMatchRows:
    """One rule, "occupying = confirmed or pending", applied by every path."""

    def test_after_every_kind_of_transition(self, db, org, membership_type):
        activity, price = _activity(db, payment_flow=PAY, max_participants=3)
        free = ActivityPrice(
            activity_id=activity.id, name="Free", amount=0, is_active=True
        )
        db.add(free)
        db.flush()
        members = [_member(db, membership_type, f"c{i}") for i in range(6)]

        a = register_member(db, activity, members[0], price.id)
        b = register_member(db, activity, members[1], free.id)
        c = register_member(db, activity, members[2], price.id)
        d = register_member(db, activity, members[3], price.id)
        e = register_member(db, activity, members[4], free.id)
        assert [r.status for r in (a, b, c, d, e)] == [
            "pending", "confirmed", "pending", "waitlist", "waitlist",
        ]
        _assert_counters_match_rows(db, activity)

        cancel_registration(db, a)
        _assert_counters_match_rows(db, activity)

        admin_change_status(db, c, "waitlist")
        _assert_counters_match_rows(db, activity)

        admin_change_status(db, b, "cancelled")
        _assert_counters_match_rows(db, activity)

        admin_change_status(db, b, "pending")
        _assert_counters_match_rows(db, activity)

        register_member(db, activity, members[5], price.id)
        _assert_counters_match_rows(db, activity)


class TestEmails:
    def test_a_pending_seat_sends_the_pending_mail_and_the_receipt_after_commit(
        self, db, org, membership_type
    ):
        org.currency = "EUR"
        activity, price = _activity(db, payment_flow=PAY)
        activity.payment_methods = ["cash"]
        member = _member(db, membership_type, "e1")

        with patch(
            "app.tasks.email_tasks.send_pending_payment_email_task.delay"
        ) as pending, patch(
            "app.tasks.email_tasks.send_receipt_email_task.delay"
        ) as receipt_mail, patch(
            "app.tasks.email_tasks.send_registration_email_task.delay"
        ) as confirmation:
            registration = register_member(db, activity, member, price.id)
            pending.assert_not_called()
            receipt_mail.assert_not_called()
            db.commit()

        [receipt] = _receipts_for(db, registration)
        receipt_mail.assert_called_once_with(receipt.id)
        confirmation.assert_not_called()
        kwargs = pending.call_args.kwargs
        assert kwargs["amount"] == f"{receipt.total_amount:.2f}"
        assert kwargs["cash"] is True
        assert kwargs["pay_now_url"] is None
        assert kwargs["deadline"] is None

    @pytest.mark.parametrize("locale", ["es", "ca", "en"])
    def test_the_pending_mail_renders_every_way_to_pay(self, locale):
        html = render_template(
            "registration_pending_payment",
            locale,
            {
                "member_name": "Ana",
                "activity_name": "Yoga",
                "amount": "27.50",
                "currency": "EUR",
                "deadline": "20/11/2026 18:00",
                "pay_now_url": "https://club.example/es/my-receipts",
                "bank_details": "Banc — ES00 0000",
                "cash": True,
            },
        )

        for fragment in ("Yoga", "27.50", "20/11/2026 18:00", "my-receipts", "ES00 0000"):
            assert fragment in html


class TestLegacyIsUnchanged:
    def test_a_paid_registration_is_confirmed_and_billed_as_before(
        self, db, org, membership_type
    ):
        activity, price = _activity(db)

        with patch(
            "app.tasks.email_tasks.send_receipt_email_task.delay"
        ) as receipt_mail, patch(
            "app.tasks.email_tasks.send_pending_payment_email_task.delay"
        ) as pending:
            registration = register_member(
                db, activity, _member(db, membership_type, "l1"), price.id
            )
            db.commit()

        assert registration.status == "confirmed"
        assert registration.payment_due_at is None
        [receipt] = _receipts_for(db, registration)
        assert receipt.status == "emitted"
        assert receipt.due_date is None
        assert receipt.is_batchable is True
        receipt_mail.assert_not_called()
        pending.assert_not_called()

    def test_auto_cancel_settings_do_not_reach_it(self, db, org, membership_type):
        _auto_cancel(org)
        activity, price = _activity(db)

        registration = register_member(
            db, activity, _member(db, membership_type, "l2"), price.id
        )

        assert registration.status == "confirmed"
        assert registration.payment_due_at is None

    def test_it_publishes_without_payment_methods(self, db, org):
        activity, _ = _activity(db)
        activity.status = "draft"

        assert publish_activity(db, activity).status == "published"


class TestPublishingAPaidActivity:
    def _draft(self, db, methods):
        activity, _ = _activity(db, payment_flow=PAY)
        activity.status = "draft"
        activity.payment_methods = methods
        db.flush()
        db.refresh(activity)
        return activity

    def test_needs_a_payment_method(self, db, org):
        with pytest.raises(HTTPException) as exc:
            publish_activity(db, self._draft(db, []))
        assert exc.value.status_code == 400

    @pytest.mark.parametrize("method", ["card", "bizum", "transfer"])
    def test_refuses_a_method_the_club_cannot_take(self, db, org, method):
        org.bank_iban = None
        with pytest.raises(HTTPException) as exc:
            publish_activity(db, self._draft(db, [method]))
        assert method in exc.value.detail

    def test_accepts_a_transfer_when_the_club_has_an_iban(self, db, org):
        org.bank_iban = "ES9121000418450200051332"
        assert publish_activity(db, self._draft(db, ["transfer"])).status == "published"

    def test_accepts_cash(self, db, org):
        assert publish_activity(db, self._draft(db, ["cash"])).status == "published"

    def test_a_free_activity_needs_no_method(self, db, org):
        activity, _ = _activity(db, payment_flow=PAY, amount=Decimal("0"))
        activity.status = "draft"
        assert publish_activity(db, activity).status == "published"
