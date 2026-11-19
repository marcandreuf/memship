"""Auto-cancel cannot be switched on behind the members' backs (#591, Q12).

The three mails that warn a member about an unpaid seat are ``operational``, and
operational mails are off until the club switches them on — so an install that
upgrades has none of them. Turning auto-cancel on then would release seats with
no word to anyone. These tests hold that it is refused instead.
"""

import pytest

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.activities.registration_service import register_member
from app.domains.auth.models import User
from app.domains.billing.seats import SEAT_PAYMENT_TEMPLATES
from tests.integration.api.v1.test_activities import _activity_payload
from tests.integration.test_receipt_payment import _auth_cookie, _create_admin
from tests.integration.test_registration_billing import (
    _activity,
    _member,
    _receipts_for,
    membership_type,  # noqa: F401 — fixture
    org,  # noqa: F401 — fixture
)


def _switch(org, keys, enabled=True):
    templates = dict((org.communications_config or {}).get("templates") or {})
    templates.update({k: {"enabled": enabled} for k in keys})
    org.communications_config = {"templates": templates}


class TestTheClubDefault:
    def test_is_refused_while_a_warning_mail_is_off(self, client, db, org):
        _switch(org, SEAT_PAYMENT_TEMPLATES[:2])
        db.flush()
        admin = _create_admin(db, "guard-club-off")

        resp = client.put(
            "/api/v1/settings/",
            json={"features": {"activity_auto_cancel_enabled": True}},
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "auto_cancel_needs_emails"
        assert SEAT_PAYMENT_TEMPLATES[2] in resp.json()["detail"]["templates"]

    def test_is_accepted_once_all_three_are_on(self, client, db, org):
        _switch(org, SEAT_PAYMENT_TEMPLATES)
        db.flush()
        admin = _create_admin(db, "guard-club-on")

        resp = client.put(
            "/api/v1/settings/",
            json={"features": {"activity_auto_cancel_enabled": True}},
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 200, resp.text

    def test_an_unrelated_save_is_not_blocked_once_it_is_on(self, client, db, org):
        org.features = {"activity_auto_cancel_enabled": True}
        db.flush()
        admin = _create_admin(db, "guard-club-later")

        resp = client.put(
            "/api/v1/settings/",
            json={"features": {"activity_auto_cancel_enabled": True, "reminder_max_count": 2}},
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 200, resp.text


class TestTheActivityOverride:
    def test_is_refused_at_creation_while_a_warning_mail_is_off(self, client, db, org):
        admin = _create_admin(db, "guard-act-create")

        resp = client.post(
            "/api/v1/activities/",
            json=_activity_payload(auto_cancel_enabled=True),
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 400

    def test_is_refused_when_switched_on_later(self, client, db, org):
        admin = _create_admin(db, "guard-act-update")
        created = client.post(
            "/api/v1/activities/", json=_activity_payload(), cookies=_auth_cookie(admin)
        ).json()

        resp = client.put(
            f"/api/v1/activities/{created['id']}",
            json={"auto_cancel_enabled": True},
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 400

    def test_switching_it_off_is_always_allowed(self, client, db, org):
        admin = _create_admin(db, "guard-act-off")

        resp = client.post(
            "/api/v1/activities/",
            json=_activity_payload(auto_cancel_enabled=False),
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 201, resp.text

    def test_is_accepted_once_all_three_are_on(self, client, db, org):
        _switch(org, SEAT_PAYMENT_TEMPLATES)
        db.flush()
        admin = _create_admin(db, "guard-act-on")

        resp = client.post(
            "/api/v1/activities/",
            json=_activity_payload(auto_cancel_enabled=True, auto_cancel_hours=24),
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 201, resp.text


class TestThePaymentOptions:
    def test_tell_the_form_what_it_may_offer_and_what_is_off(self, client, db, org):
        org.bank_iban = "ES9121000418450200051332"
        org.features = {"activity_auto_cancel_hours": 36}
        _switch(org, SEAT_PAYMENT_TEMPLATES[:1])
        db.flush()
        admin = _create_admin(db, "options")

        data = client.get(
            "/api/v1/activities/payment-options", cookies=_auth_cookie(admin)
        ).json()

        assert data["usable_methods"] == ["transfer", "cash"]
        assert data["auto_cancel_enabled"] is False
        assert data["auto_cancel_hours"] == 36
        assert data["switched_off_templates"] == list(SEAT_PAYMENT_TEMPLATES[1:])


class TestAMemberCancellingAPendingSeat:
    def test_is_allowed_and_voids_the_receipt(self, client, db, org, membership_type):
        activity, price = _activity(db, payment_flow="pay_to_confirm")
        activity.allow_self_cancellation = True
        member = _member(db, membership_type, "self-pending")
        registration = register_member(db, activity, member, price.id)
        user = User(
            party_id=member.party_id,
            email=member.person.email,
            password_hash=hash_password("password123"),
            role="member",
            is_active=True,
        )
        db.add(user)
        db.flush()
        member.user_id = user.id
        db.flush()

        resp = client.delete(
            f"/api/v1/registrations/{registration.id}",
            cookies={"access_token": create_access_token(user.id)},
        )

        assert resp.status_code == 204, resp.text
        db.refresh(registration)
        assert registration.status == "cancelled"
        assert [r.status for r in _receipts_for(db, registration)] == ["cancelled"]


@pytest.mark.parametrize("key", SEAT_PAYMENT_TEMPLATES)
def test_every_warning_mail_is_catalogued_as_operational(key):
    from app.domains.mailing.policy import BY_KEY

    assert BY_KEY[key].tier == "operational"
