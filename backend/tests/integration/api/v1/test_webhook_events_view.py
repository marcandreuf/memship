"""The admin view of recorded payment notifications (#435)."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.billing.models import Receipt, WebhookEvent
from app.domains.persons.models import Person

URL = "/api/v1/payment-providers/webhook-events"
T0 = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


def _user(db, role, suffix="wev"):
    person = Person(first_name="Test", last_name="User", email=f"{suffix}-{role}@examplee6e3b1.com")
    db.add(person)
    db.flush()
    user = User(
        party_id=person.party_id,
        email=f"{suffix}-{role}@examplee6e3b1.com",
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _cookie(user):
    return {"access_token": create_access_token(user.id)}


def _event(db, n, status, provider="stripe", error=None, receipt=None, minutes=0):
    event = WebhookEvent(
        provider_type=provider,
        external_event_id=f"evt_wev_{n}",
        event_type="checkout.session.completed",
        payload={"customer_email": "member@examplee6e3b1.com", "amount_total": 5000},
        status=status,
        error_message=error,
        receipt_id=receipt.id if receipt else None,
        created_at=T0 + timedelta(minutes=minutes),
    )
    db.add(event)
    db.flush()
    return event


def _receipt(db, owner):
    receipt = Receipt(
        receipt_number="FAC-WEV-1",
        party_id=owner.party_id,
        origin="membership",
        description="Membership fee",
        base_amount=Decimal("50.00"),
        vat_rate=Decimal("0.00"),
        vat_amount=Decimal("0.00"),
        total_amount=Decimal("50.00"),
        status="paid",
        emission_date=date(2026, 10, 1),
    )
    db.add(receipt)
    db.flush()
    return receipt


class TestAccess:
    def test_requires_integrations_permission(self, client, db):
        member = _user(db, "member")
        assert client.get(URL, cookies=_cookie(member)).status_code == 403

    def test_requires_a_session(self, client):
        assert client.get(URL).status_code == 401


class TestListing:
    def test_defaults_to_failed_and_ignored_newest_first(self, client, db):
        admin = _user(db, "super_admin")
        _event(db, 1, "processed", minutes=0)
        _event(db, 2, "failed", error="Receipt not found", minutes=1)
        _event(db, 3, "ignored", error="Receipt already paid", minutes=2)
        _event(db, 4, "received", minutes=3)

        body = client.get(URL, cookies=_cookie(admin)).json()

        assert [e["external_event_id"] for e in body["items"]] == ["evt_wev_3", "evt_wev_2"]
        assert body["items"][0]["error_message"] == "Receipt already paid"
        assert body["meta"]["total"] == 2

    def test_the_payload_is_not_exposed(self, client, db):
        admin = _user(db, "super_admin")
        _event(db, 1, "failed")

        item = client.get(URL, cookies=_cookie(admin)).json()["items"][0]

        assert "payload" not in item
        assert "member@examplee6e3b1.com" not in str(item)

    def test_an_ignored_double_charge_names_its_receipt(self, client, db):
        admin = _user(db, "super_admin")
        _event(db, 1, "ignored", error="Receipt already paid", receipt=_receipt(db, admin))

        item = client.get(URL, cookies=_cookie(admin)).json()["items"][0]

        assert item["receipt_number"] == "FAC-WEV-1"
        assert item["receipt_id"] is not None

    def test_filters_by_status_and_provider(self, client, db):
        admin = _user(db, "super_admin")
        _event(db, 1, "processed", provider="stripe")
        _event(db, 2, "processed", provider="redsys")
        _event(db, 3, "failed", provider="redsys")

        body = client.get(
            URL,
            params=[("status", "processed"), ("provider_type", "redsys")],
            cookies=_cookie(admin),
        ).json()

        assert [e["external_event_id"] for e in body["items"]] == ["evt_wev_2"]

    def test_an_unknown_status_is_refused(self, client, db):
        admin = _user(db, "super_admin")
        response = client.get(URL, params={"status": "lost"}, cookies=_cookie(admin))
        assert response.status_code == 422

    def test_does_not_shadow_a_provider_by_id(self, client, db):
        """Declared before `/{provider_id}`, which would otherwise try to read
        `webhook-events` as an id."""
        admin = _user(db, "super_admin")
        assert client.get(URL, cookies=_cookie(admin)).status_code == 200
        assert client.get(f"{URL[:-len('webhook-events')]}999999", cookies=_cookie(admin)).status_code == 404
