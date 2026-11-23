"""A seat freed on a pay-to-confirm activity goes to the waiting list as pending (#591)."""

from unittest.mock import patch

import pytest

from app.core.email import render_template
from app.domains.activities.models import ActivityPrice
from app.domains.activities.registration_service import (
    cancel_registration,
    register_member,
)
from app.domains.billing.seats import SEAT_PAYMENT_TEMPLATES
from app.tasks.email_tasks import send_pending_payment_email_task
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
PENDING = "app.tasks.email_tasks.send_pending_payment_email_task.delay"


def _full(db, membership_type, suffix, **kwargs):
    activity, price = _activity(db, payment_flow=PAY, max_participants=1, **kwargs)
    holder = register_member(
        db, activity, _member(db, membership_type, f"{suffix}-h"), price.id
    )
    return activity, price, holder


def _sent_to(delay, registration):
    """The mails a patched ``.delay`` queued for this registration's member;
    the holder's own pending-payment mail is queued too, and lands at the same
    commit."""
    email = registration.member.person.email
    return [c.kwargs for c in delay.call_args_list if c.kwargs["to"] == email]


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

        with patch(PROMOTION) as promoted, patch(PENDING) as pending:
            cancel_registration(db, holder)
            db.commit()

        promoted.assert_not_called()
        [mail] = _sent_to(pending, waiting)
        [receipt] = _receipts_for(db, waiting)
        assert mail["promoted"] is True
        assert mail["amount"] == f"{receipt.total_amount:.2f}"
        assert mail["cash"] is True


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

        with patch(PROMOTION) as promoted, patch(PENDING) as pending:
            cancel_registration(db, holder)
            db.commit()

        assert waiting.status == "confirmed"
        assert _receipts_for(db, waiting) == []
        assert len(_sent_to(promoted, waiting)) == 1
        assert _sent_to(pending, waiting) == []


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

        with patch(PROMOTION) as promoted, patch(PENDING) as pending:
            cancel_registration(db, holder)
            db.commit()

        assert waiting.status == "confirmed"
        assert waiting.payment_due_at is None
        [receipt] = _receipts_for(db, waiting)
        assert (receipt.is_batchable, receipt.due_date) == (True, None)
        assert len(_sent_to(promoted, waiting)) == 1
        assert _sent_to(pending, waiting) == []


class TestThePromotedMemberIsAlwaysTold:
    """The mail that tells a promotee they must pay is one a pay-to-confirm
    activity cannot run without: seeded on, and refused to be switched off
    while a seat can be released unpaid. waitlist_promoted is neither, and was
    what this used to send, so with the default configuration a promotee was
    told nothing until the cancellation for non-payment (#619). Held end to
    end: the dispatcher, the task, the template."""

    def test_through_a_template_auto_cancel_keeps_on(self, db, org, membership_type):
        _auto_cancel(org, hours=24)
        activity, price, holder = _full(db, membership_type, "told")
        waiting = register_member(
            db, activity, _member(db, membership_type, "told-w"), price.id
        )
        queued = []

        with (
            patch(PROMOTION, side_effect=lambda **kw: queued.append(kw)),
            patch(PENDING, side_effect=lambda **kw: queued.append(kw)),
        ):
            cancel_registration(db, holder)
            db.commit()
        [promotion] = [
            kw for kw in queued if kw["to"] == waiting.member.person.email
        ]

        with patch("app.core.email._send_templated", return_value=True) as send:
            send_pending_payment_email_task.run(**promotion)

        assert send.call_args.args[0] in SEAT_PAYMENT_TEMPLATES
        assert send.call_args.args[3]["promoted"] is True


@pytest.mark.parametrize(
    "locale,heading",
    [("es", "Hay una plaza para ti"), ("ca", "Hi ha una plaça per a tu"), ("en", "A seat is yours")],
)
def test_the_promotion_mail_renders_with_payment(locale, heading):
    html = render_template(
        "registration_pending_payment",
        locale,
        {
            "promoted": True,
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

    amount = {"es": "27,50 €", "ca": "27,50 €", "en": "€27.50"}[locale]
    for fragment in (heading, "Yoga", amount, "20/11/2026 18:00", "my-receipts", "ES00 0000"):
        assert fragment in html
