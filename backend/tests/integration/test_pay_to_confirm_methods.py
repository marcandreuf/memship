"""Which ways to pay a member is offered, and that they match the activity (#591).

SEPA direct debit counted as an online provider, so a club with only SEPA live
could publish card and Bizum activities and email "Pay now" buttons nobody could
use. And a pay-to-confirm seat's receipt offered every method the club takes,
not the ones its activity accepts.
"""

import pytest

from app.domains.activities.payment import seat_payment_instructions, unusable_methods
from app.domains.billing.models import PaymentProvider
from app.domains.billing.payment_instructions import (
    delivery_instructions,
    how_to_pay,
    online_methods_available,
    receipt_allowed_methods,
    receipt_instructions,
)
from tests.integration.api.v1.test_redsys_flow import _create_redsys_provider
from tests.integration.test_pay_to_confirm_payment import _pending, _stripe_provider
from tests.integration.test_receipt_payment import _auth_cookie, _create_admin
from tests.integration.test_registration_billing import (
    _activity,
    _member,
    _receipts_for,
    membership_type,  # noqa: F401 — fixture
    org,  # noqa: F401 — fixture
)
from app.domains.activities.registration_service import register_member

IBAN = "ES9121000418450200051332"


def _sepa_provider(db):
    db.add(
        PaymentProvider(
            provider_type="sepa_direct_debit",
            display_name="SEPA",
            status="active",
            config={"format": "pain.008.001.02"},
        )
    )
    db.flush()


class TestOnlineMethodsAvailable:
    def test_sepa_alone_offers_no_online_method(self, db, org):
        _sepa_provider(db)

        assert online_methods_available(db) == set()
        assert unusable_methods(db, ["card", "bizum"]) == ["card", "bizum"]

    def test_stripe_offers_card_but_not_bizum(self, db, org):
        _stripe_provider(db)

        assert online_methods_available(db) == {"card"}
        assert unusable_methods(db, ["card", "bizum"]) == ["bizum"]

    def test_redsys_offers_bizum_only_where_enabled(self, db, org):
        _create_redsys_provider(db, enable_bizum=True)

        assert online_methods_available(db) == {"card", "bizum"}

    def test_a_disabled_provider_offers_nothing(self, db, org):
        _create_redsys_provider(db, status="disabled", enable_bizum=True)

        assert online_methods_available(db) == set()

    def test_a_club_receipt_with_only_sepa_shows_the_bank_details(self, db, org):
        _sepa_provider(db)
        org.bank_iban = IBAN

        got = how_to_pay(db, org, "es")

        assert got.pay_now_url is None
        assert IBAN in got.bank_details


def _seat_receipt(db, membership_type, suffix, methods):
    activity, registration, receipt = _pending(db, membership_type, suffix)
    activity.payment_methods = methods
    db.flush()
    return activity, registration, receipt


class TestASeatReceiptOffersWhatItsActivityAccepts:
    def test_cash_only_offers_no_button_and_no_bank_details(self, db, org, membership_type):
        _stripe_provider(db)
        org.bank_iban = IBAN
        _, _, receipt = _seat_receipt(db, membership_type, "m-cash", ["cash"])

        got = delivery_instructions(db, receipt, org, "es")

        assert got.pay_now_url is None
        assert got.bank_details is None
        assert got.cash

    def test_card_and_transfer_offer_both(self, db, org, membership_type):
        _stripe_provider(db)
        org.bank_iban = IBAN
        _, _, receipt = _seat_receipt(db, membership_type, "m-both", ["card", "transfer"])

        got = receipt_instructions(db, receipt, org, "es")

        assert got.pay_now_url.endswith("/es/my-receipts")
        assert IBAN in got.bank_details
        assert not got.cash

    def test_a_card_activity_with_only_sepa_live_offers_no_button(
        self, db, org, membership_type
    ):
        _sepa_provider(db)
        activity, _, _ = _seat_receipt(db, membership_type, "m-sepa", ["card"])

        assert seat_payment_instructions(db, activity, "es").pay_now_url is None

    def test_a_legacy_receipt_is_unrestricted(self, db, org, membership_type):
        activity, price = _activity(db)
        registration = register_member(db, activity, _member(db, membership_type, "m-leg"), price.id)
        [receipt] = _receipts_for(db, registration)

        assert receipt_allowed_methods(receipt) is None

    def test_the_seat_receipt_lists_the_activity_methods(self, db, org, membership_type):
        _, _, receipt = _seat_receipt(db, membership_type, "m-list", ["cash", "transfer"])

        assert receipt_allowed_methods(receipt) == ["cash", "transfer"]


class TestTheGatewayRefusesAMethodTheActivityDoesNotAccept:
    @pytest.mark.parametrize(
        "path, body",
        [("stripe/checkout", None), ("redsys/initiate", {"method": "card"})],
    )
    def test_card_on_a_cash_only_seat(self, client, db, org, membership_type, path, body):
        _stripe_provider(db)
        _create_redsys_provider(db)
        _, _, receipt = _seat_receipt(db, membership_type, f"m-gw-{path[:6]}", ["cash"])
        admin = _create_admin(db, f"p2c-gw-{path[:6]}")
        db.commit()

        resp = client.post(
            f"/api/v1/receipts/{receipt.id}/{path}", json=body, cookies=_auth_cookie(admin)
        )

        assert resp.status_code == 400, resp.text
        assert resp.json()["detail"] == {"code": "payment_method_not_accepted", "method": "card"}
