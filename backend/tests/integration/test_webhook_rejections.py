"""Notifications refused at the signature check, and the daily digest (#514)."""

import hashlib
import hmac
import json
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.core.email import render_template
from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.billing import webhook_rejections
from app.domains.billing.models import PaymentProvider, Receipt, WebhookEvent
from app.domains.billing.providers.stripe_provider import StripeAdapter
from app.domains.billing.webhook_digest import MAX_LISTED, build_digest
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person
from app.tasks.billing_tasks import scheduled_webhook_digest

SECRET = "whsec_test_rejections"
NOW = datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _own_prefix(monkeypatch):
    """Each test counts in keys of its own, so counts never leak between tests."""
    monkeypatch.setattr(
        webhook_rejections, "KEY_PREFIX", f"memship:webhook-rejections:test:{uuid.uuid4().hex}"
    )


def _stripe_provider(db):
    provider = PaymentProvider(
        provider_type="stripe",
        display_name="Stripe",
        status="test",
        config={"webhook_secret": SECRET, "secret_key": "sk_test_x", "publishable_key": "pk_test_x"},
        is_default=False,
    )
    db.add(provider)
    db.flush()
    return provider


def _signed(payload: str, secret: str = SECRET) -> str:
    t = int(time.time())
    mac = hmac.new(secret.encode(), f"{t}.{payload}".encode(), hashlib.sha256).hexdigest()
    return f"t={t},v1={mac}"


def _admin(db):
    person = Person(first_name="A", last_name="Dmin", email="rej-admin@examplee6e3b1.com")
    db.add(person)
    db.flush()
    user = User(
        party_id=person.party_id,
        email="rej-admin@examplee6e3b1.com",
        password_hash=hash_password("password123"),
        role="super_admin",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _event(db, n, status, created_at, error="boom", receipt=None):
    event = WebhookEvent(
        provider_type="stripe",
        external_event_id=f"evt_rej_{n}",
        event_type="checkout.session.completed",
        payload={},
        status=status,
        error_message=error,
        receipt_id=receipt.id if receipt else None,
        created_at=created_at,
    )
    db.add(event)
    db.flush()
    return event


def _org(db, address="tesoreria@examplee6e3b1.com"):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(
            id=1,
            name="Test Organization",
            locale="es",
            timezone="Europe/Madrid",
            currency="EUR",
            date_format="DD/MM/YYYY",
            invoice_prefix="FAC",
            invoice_next_number=1,
            invoice_annual_reset=True,
            default_vat_rate=21.00,
        )
        db.add(org)
    features = dict(org.features or {})
    if address:
        features["billing_notification_email"] = address
    else:
        features.pop("billing_notification_email", None)
    org.features = features
    db.flush()
    return org


class TestCounting:
    def test_a_rejection_is_counted_with_its_reason(self):
        webhook_rejections.record_rejection("stripe", "Invalid signature: no match")
        webhook_rejections.record_rejection("stripe", "Invalid signature: expired")

        [summary] = webhook_rejections.rejection_summaries(
            ["stripe", "redsys"], datetime.now(timezone.utc) - timedelta(hours=1)
        )

        assert summary.provider_type == "stripe"
        assert summary.count == 2
        assert summary.last_reason == "Invalid signature: expired"
        assert summary.last_at is not None

    def test_the_set_is_capped(self, monkeypatch):
        monkeypatch.setattr(webhook_rejections, "MAX_TRACKED", 5)
        for _ in range(12):
            webhook_rejections.record_rejection("stripe", "Invalid signature")

        [summary] = webhook_rejections.rejection_summaries(
            ["stripe"], datetime.now(timezone.utc) - timedelta(hours=1)
        )

        assert summary.count == 5

    def test_an_old_rejection_is_outside_the_window(self):
        webhook_rejections.record_rejection("stripe", "Invalid signature")

        assert webhook_rejections.rejection_summaries(
            ["stripe"], datetime.now(timezone.utc) + timedelta(minutes=1)
        ) == []

    def test_redis_down_reports_unavailable_and_does_not_raise(self):
        import redis

        with patch.object(webhook_rejections, "_client", side_effect=redis.ConnectionError("down")):
            webhook_rejections.record_rejection("stripe", "Invalid signature")
            assert webhook_rejections.rejection_summaries(["stripe"], NOW) is None


class TestTheWebhookEndpoint:
    def test_a_bad_signature_is_counted_and_writes_no_row(self, client, db):
        _stripe_provider(db)
        body = json.dumps({"id": "evt_bad", "object": "event", "type": "customer.created"})

        resp = client.post(
            "/api/v1/webhooks/stripe",
            content=body,
            headers={"content-type": "application/json", "stripe-signature": _signed(body, "whsec_wrong")},
        )

        assert resp.status_code == 400
        assert db.query(WebhookEvent).filter(WebhookEvent.external_event_id == "evt_bad").count() == 0
        [summary] = webhook_rejections.rejection_summaries(
            ["stripe"], datetime.now(timezone.utc) - timedelta(hours=1)
        )
        assert summary.count == 1
        assert "Invalid signature" in summary.last_reason

    def test_a_signed_body_that_is_not_an_event_is_a_400_not_a_500(self, client, db):
        """It used to raise AttributeError out of the SDK and answer 500."""
        _stripe_provider(db)
        body = json.dumps({"id": "evt_shapeless", "type": "customer.created"})

        resp = client.post(
            "/api/v1/webhooks/stripe",
            content=body,
            headers={"content-type": "application/json", "stripe-signature": _signed(body)},
        )

        assert resp.status_code == 400

    def test_the_adapter_names_the_shapeless_body(self):
        body = json.dumps({"id": "evt_shapeless"})
        with pytest.raises(ValueError, match="Not a Stripe event"):
            StripeAdapter({"webhook_secret": SECRET}).verify_signature(
                {"stripe-signature": _signed(body)}, body.encode()
            )


class TestTheRejectionsEndpoint:
    URL = "/api/v1/payment-providers/webhook-rejections"

    def test_lists_configured_providers_with_rejections(self, client, db):
        _stripe_provider(db)
        webhook_rejections.record_rejection("stripe", "Invalid signature")
        admin = _admin(db)

        body = client.get(self.URL, cookies={"access_token": create_access_token(admin.id)}).json()

        assert body["available"] is True
        assert body["days"] == 7
        assert [(i["provider_type"], i["count"]) for i in body["items"]] == [("stripe", 1)]
        assert body["items"][0]["last_reason"] == "Invalid signature"

    def test_reports_unavailable_when_redis_is(self, client, db):
        _stripe_provider(db)
        admin = _admin(db)
        with patch.object(webhook_rejections, "rejection_summaries", return_value=None):
            body = client.get(self.URL, cookies={"access_token": create_access_token(admin.id)}).json()
        assert body == {"available": False, "days": 7, "items": []}

    def test_requires_integrations_permission(self, client, db):
        person = Person(first_name="M", last_name="Ember", email="rej-member@examplee6e3b1.com")
        db.add(person)
        db.flush()
        member = User(
            party_id=person.party_id,
            email="rej-member@examplee6e3b1.com",
            password_hash=hash_password("password123"),
            role="member",
            is_active=True,
        )
        db.add(member)
        db.flush()
        resp = client.get(self.URL, cookies={"access_token": create_access_token(member.id)})
        assert resp.status_code == 403


class TestDigest:
    def test_collects_the_last_day_of_failed_and_ignored(self, db):
        _stripe_provider(db)
        _event(db, 1, "failed", NOW - timedelta(hours=2), error="Receipt not found")
        _event(db, 2, "ignored", NOW - timedelta(hours=1), error="Receipt already paid")
        _event(db, 3, "processed", NOW - timedelta(hours=1))
        _event(db, 4, "failed", NOW - timedelta(hours=30))

        digest = build_digest(db, NOW, "Europe/Madrid")

        assert digest.events_total == 2
        assert [e["status"] for e in digest.events] == ["ignored", "failed"]
        # 07:00 UTC is 08:00 in Madrid in November.
        assert digest.events[0]["at"] == "2026-11-03 08:00"

    def test_names_the_receipt_of_an_ignored_double_charge(self, db):
        _stripe_provider(db)
        owner = _admin(db)
        receipt = Receipt(
            receipt_number="FAC-REJ-1",
            party_id=owner.party_id,
            origin="manual",
            description="Fee",
            base_amount=Decimal("10.00"),
            vat_rate=Decimal("0.00"),
            vat_amount=Decimal("0.00"),
            total_amount=Decimal("10.00"),
            status="paid",
            emission_date=date(2026, 11, 1),
        )
        db.add(receipt)
        db.flush()
        _event(db, 1, "ignored", NOW - timedelta(hours=1), "Receipt already paid", receipt)

        assert build_digest(db, NOW).events[0]["receipt_number"] == "FAC-REJ-1"

    def test_lists_at_most_max_listed_and_counts_the_rest(self, db):
        _stripe_provider(db)
        for n in range(MAX_LISTED + 3):
            _event(db, n, "failed", NOW - timedelta(minutes=n + 1))

        digest = build_digest(db, NOW)

        assert digest.events_total == MAX_LISTED + 3
        assert len(digest.events) == MAX_LISTED

    def test_includes_rejections(self, db):
        _stripe_provider(db)
        webhook_rejections.record_rejection("stripe", "Invalid signature")

        digest = build_digest(db, datetime.now(timezone.utc))

        assert digest.rejections[0]["provider"] == "stripe"
        assert digest.rejections[0]["count"] == 1
        assert not digest.is_empty

    def test_nothing_wrong_is_empty(self, db):
        _stripe_provider(db)
        _event(db, 1, "processed", NOW - timedelta(hours=1))

        assert build_digest(db, NOW).is_empty


class TestDigestTask:
    def _run(self, db):
        with (
            patch("app.db.session.SessionLocal", return_value=db),
            patch.object(db, "close"),
            patch("app.core.email.send_webhook_digest_email", return_value=True) as send,
        ):
            result = scheduled_webhook_digest.run()
        return result, send

    def test_sends_to_the_billing_notification_address(self, db):
        _org(db)
        _stripe_provider(db)
        _event(db, 1, "failed", datetime.now(timezone.utc) - timedelta(hours=1))

        result, send = self._run(db)

        assert result["sent"] is True
        assert send.call_args.args[0] == "tesoreria@examplee6e3b1.com"
        assert send.call_args.args[2] == 1

    def test_silent_without_an_address(self, db):
        _org(db, address=None)
        _event(db, 1, "failed", datetime.now(timezone.utc) - timedelta(hours=1))

        result, send = self._run(db)

        assert result == {"sent": False, "reason": "no_address"}
        send.assert_not_called()

    def test_silent_when_nothing_went_wrong(self, db):
        _org(db)

        result, send = self._run(db)

        assert result == {"sent": False, "reason": "nothing_to_report"}
        send.assert_not_called()


class TestDigestTemplate:
    CONTEXT = {
        "events": [
            {
                "at": "2026-11-03 08:00",
                "provider": "stripe",
                "event_type": "checkout.session.completed",
                "status": "ignored",
                "reason": "Receipt already paid",
                "receipt_number": "FAC-REJ-1",
            }
        ],
        "events_total": 3,
        "events_hidden": 2,
        "rejections": [{"provider": "redsys", "count": 40, "last_at": "", "last_reason": "Invalid Redsys signature"}],
        "rejected_total": 40,
    }

    @pytest.mark.parametrize(
        "locale,heading,ignored,more",
        [
            ("es", "Notificaciones de pago con incidencias", "ignorada", "Y 2 más"),
            ("ca", "Notificacions de pagament amb incidències", "ignorada", "I 2 més"),
            ("en", "Payment notifications needing attention", "ignored", "And 2 more"),
        ],
    )
    def test_renders_events_and_rejections(self, locale, heading, ignored, more):
        html = render_template("webhook_digest", locale, dict(self.CONTEXT))

        assert heading in html
        assert "FAC-REJ-1" in html
        assert f"{ignored}: Receipt already paid" in html
        assert "40 — Invalid Redsys signature" in html
        assert more in html
