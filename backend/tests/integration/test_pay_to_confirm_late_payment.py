"""A payment that arrives after its seat was released is recorded, not lost (#591).

The gateway answers 200 either way, as before; what changes is that the money is
on the books, the seat is given back if one is free, and the club is told.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.domains.activities.models import Registration
from app.domains.activities.registration_service import register_member
from app.domains.billing.models import Receipt
from app.domains.billing.seats import expire_unpaid_seats, record_late_payment
from app.domains.billing.service import VALID_TRANSITIONS
from tests.integration.api.v1.test_redsys_flow import (
    _create_redsys_provider,
    _post_webhook,
    _sign_notification,
)
from tests.integration.test_pay_to_confirm_payment import (
    _post_stripe_paid,
    _stripe_provider,
)
from tests.integration.test_pay_to_confirm_registration import (
    _assert_counters_match_rows,
    _auto_cancel,
)
from tests.integration.test_receipt_payment import _auth_cookie, _create_admin
from tests.integration.test_registration_billing import (
    _activity,
    _member,
    _receipts_for,
    membership_type,  # noqa: F401 — fixture
    org,  # noqa: F401 — fixture
)

ALERT = "app.tasks.email_tasks.send_late_payment_alert_email_task.delay"
LATER = datetime.now(timezone.utc) + timedelta(days=30)


def _released(db, org, membership_type, suffix, *, taken=False):
    """A seat released unpaid; with ``taken``, a waitlister now holds it."""
    _auto_cancel(org, hours=2)
    org.features = {**org.features, "billing_notification_email": "treasurer@club.example"}
    activity, price = _activity(db, payment_flow="pay_to_confirm", max_participants=1)
    registration = register_member(
        db, activity, _member(db, membership_type, suffix), price.id
    )
    if taken:
        register_member(db, activity, _member(db, membership_type, f"{suffix}-w"), price.id)
    [receipt] = _receipts_for(db, registration)
    expire_unpaid_seats(db, LATER)
    assert (registration.status, receipt.status) == ("cancelled", "cancelled")
    return activity, registration, receipt


def _reload(db, registration):
    db.expire_all()
    return db.query(Registration).filter(Registration.id == registration.id).one()


class TestWithASeatFree:
    def test_stripe_records_it_and_gives_the_seat_back(
        self, client, db, org, membership_type
    ):
        activity, registration, receipt = _released(db, org, membership_type, "free")
        _stripe_provider(db)

        with patch(ALERT) as alert:
            resp = _post_stripe_paid(client, receipt, "late-free")

        assert resp.status_code == 200, resp.text
        db.expire_all()
        assert db.get(Receipt, receipt.id).status == "paid"
        registration = _reload(db, registration)
        assert registration.status == "confirmed"
        assert registration.refund_status == "none"
        assert registration.late_payment_at is not None
        assert alert.call_args.kwargs["seat_confirmed"] is True
        assert alert.call_args.kwargs["to"] == "treasurer@club.example"
        _assert_counters_match_rows(db, activity)


class TestWithNoSeatFree:
    def test_redsys_records_it_and_owes_it_back(self, client, db, org, membership_type):
        activity, registration, receipt = _released(
            db, org, membership_type, "taken", taken=True
        )
        receipt.redsys_ds_order = "000000591900"
        _create_redsys_provider(db)
        db.flush()

        with patch(ALERT) as alert:
            resp = _post_webhook(
                client,
                _sign_notification(
                    ds_order=receipt.redsys_ds_order,
                    ds_amount=int(receipt.total_amount * 100),
                ),
            )

        assert resp.status_code == 200, resp.text
        db.expire_all()
        assert db.get(Receipt, receipt.id).status == "paid"
        registration = _reload(db, registration)
        assert registration.status == "cancelled"
        assert registration.refund_status == "due"
        assert alert.call_args.kwargs["seat_confirmed"] is False
        _assert_counters_match_rows(db, activity)

    def test_it_is_on_the_refund_list_and_the_banner_until_seen(
        self, client, db, org, membership_type
    ):
        _, registration, receipt = _released(db, org, membership_type, "seen", taken=True)
        _stripe_provider(db)
        with patch(ALERT):
            _post_stripe_paid(client, receipt, "late-seen")
        admin = _create_admin(db, "late-seen")
        cookies = _auth_cookie(admin)

        refunds = client.get("/api/v1/registrations/refunds", cookies=cookies).json()
        banner = client.get("/api/v1/registrations/late-payments", cookies=cookies).json()
        assert registration.id in [i["registration_id"] for i in refunds["items"]]
        assert registration.id in [i["registration_id"] for i in banner["items"]]

        resp = client.post(
            f"/api/v1/registrations/{registration.id}/late-payment-seen", cookies=cookies
        )

        assert resp.status_code == 204
        banner = client.get("/api/v1/registrations/late-payments", cookies=cookies).json()
        assert registration.id not in [i["registration_id"] for i in banner["items"]]


class TestTheExceptionStaysNarrow:
    def test_cancelled_is_still_terminal(self):
        assert VALID_TRANSITIONS["cancelled"] == set()

    def test_a_receipt_that_is_not_a_seats_is_not_reopened(
        self, db, org, membership_type
    ):
        receipt = Receipt(
            receipt_number="FAC-591-NOSEAT",
            party_id=_member(db, membership_type, "noseat").party_id,
            origin="manual",
            description="Not a seat",
            base_amount=10,
            vat_rate=0,
            vat_amount=0,
            total_amount=10,
            status="cancelled",
            emission_date=datetime.now(timezone.utc).date(),
        )
        db.add(receipt)
        db.flush()

        assert record_late_payment(db, receipt, payment_method="stripe_checkout") is None
        assert receipt.status == "cancelled"

    def test_a_receipt_still_live_is_not_a_late_payment(self, db, org, membership_type):
        activity, price = _activity(db, payment_flow="pay_to_confirm")
        registration = register_member(
            db, activity, _member(db, membership_type, "live"), price.id
        )
        [receipt] = _receipts_for(db, registration)

        assert record_late_payment(db, receipt, payment_method="stripe_checkout") is None
        assert registration.late_payment_at is None
