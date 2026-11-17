"""A seat freed on a pay-to-confirm activity goes to the waiting list as pending (#591)."""

from unittest.mock import patch

import pytest

from app.core.email import render_template
from app.domains.activities.models import ActivityPrice
from app.domains.activities.registration_service import (
    cancel_registration,
    register_member,
)
from tests.integration.test_pay_to_confirm_registration import (
    _assert_counters_match_rows,
    _auto_cancel,
)
from tests.integration.test_registration_billing import (
    _activity,
    _member,
    _receipts_for,
    membership_type,  # noqa: F401 — fixture
    org,  # noqa: F401 — fixture
)

PAY = "pay_to_confirm"
PROMOTION = "app.tasks.email_tasks.send_promotion_email_task.delay"


def _full(db, membership_type, suffix, **kwargs):
    activity, price = _activity(db, payment_flow=PAY, max_participants=1, **kwargs)
    holder = register_member(
        db, activity, _member(db, membership_type, f"{suffix}-h"), price.id
    )
    return activity, price, holder


class TestAPayerIsPromotedToPending:
    def test_with_a_deadline_and_a_receipt(self, db, org, membership_type):
        _auto_cancel(org, hours=24)
        activity, price, holder = _full(db, membership_type, "pend")
        waiting = register_member(
            db, activity, _member(db, membership_type, "pend-w"), price.id
        )

        cancel_registration(db, holder)

        assert waiting.status == "pending"
        assert waiting.payment_due_at is not None
        [receipt] = _receipts_for(db, waiting)
        assert receipt.status == "emitted"
        assert receipt.is_batchable is False
        _assert_counters_match_rows(db, activity)

    def test_the_mail_says_payment_is_due_and_how(self, db, org, membership_type):
        activity, price, holder = _full(db, membership_type, "mail")
        activity.payment_methods = ["cash"]
        waiting = register_member(
            db, activity, _member(db, membership_type, "mail-w"), price.id
        )

        with patch(PROMOTION) as delay:
            cancel_registration(db, holder)
            db.commit()

        payment = delay.call_args.kwargs["payment"]
        [receipt] = _receipts_for(db, waiting)
        assert payment["amount"] == f"{receipt.total_amount:.2f}"
        assert payment["cash"] is True


class TestAnExemptPromoteeIsConfirmed:
    def test_with_no_receipt_and_no_payment_in_the_mail(
        self, db, org, membership_type
    ):
        activity, price, holder = _full(db, membership_type, "free")
        free = ActivityPrice(activity_id=activity.id, name="Free", amount=0, is_active=True)
        db.add(free)
        db.flush()
        waiting = register_member(
            db, activity, _member(db, membership_type, "free-w"), free.id
        )

        with patch(PROMOTION) as delay:
            cancel_registration(db, holder)
            db.commit()

        assert waiting.status == "confirmed"
        assert _receipts_for(db, waiting) == []
        assert delay.call_args.kwargs["payment"] is None


class TestTheCascade:
    def test_a_promoted_seat_left_unpaid_passes_to_the_next(
        self, db, org, membership_type
    ):
        activity, price, holder = _full(db, membership_type, "cascade")
        second = register_member(
            db, activity, _member(db, membership_type, "cascade-2"), price.id
        )
        third = register_member(
            db, activity, _member(db, membership_type, "cascade-3"), price.id
        )

        cancel_registration(db, holder)
        assert (second.status, third.status) == ("pending", "waitlist")

        cancel_registration(db, second)

        assert third.status == "pending"
        assert _receipts_for(db, second)[0].status == "cancelled"
        _assert_counters_match_rows(db, activity)


class TestLegacyPromotionIsUnchanged:
    def test_the_promotee_is_confirmed_and_billed(self, db, org, membership_type):
        activity, price = _activity(db, max_participants=1)
        holder = register_member(
            db, activity, _member(db, membership_type, "leg-h"), price.id
        )
        waiting = register_member(
            db, activity, _member(db, membership_type, "leg-w"), price.id
        )

        with patch(PROMOTION) as delay:
            cancel_registration(db, holder)
            db.commit()

        assert waiting.status == "confirmed"
        assert waiting.payment_due_at is None
        [receipt] = _receipts_for(db, waiting)
        assert (receipt.is_batchable, receipt.due_date) == (True, None)
        assert delay.call_args.kwargs["payment"] is None


@pytest.mark.parametrize("locale", ["es", "ca", "en"])
def test_the_promotion_mail_renders_with_payment(locale):
    html = render_template(
        "waitlist_promoted",
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
