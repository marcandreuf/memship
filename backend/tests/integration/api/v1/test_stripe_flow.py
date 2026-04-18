"""Integration tests for Stripe Checkout flow — endpoints + webhook dispatch."""

import json
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.core.encryption import encrypt_config
from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.billing.models import (
    Concept,
    PaymentProvider,
    Receipt,
    WebhookEvent,
)
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


# --- Helpers ---


def _create_org(db):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if org:
        return org
    org = OrganizationSettings(
        id=1,
        name="Test Club",
        currency="EUR",
        invoice_prefix="FAC",
        invoice_annual_reset=True,
        default_vat_rate=Decimal("21.00"),
    )
    db.add(org)
    db.flush()
    return org


def _create_person(db, email="stripe-test@example.com", suffix=""):
    person = Person(
        first_name="Stripe",
        last_name=f"Test{suffix}",
        email=f"{suffix}{email}" if suffix else email,
    )
    db.add(person)
    db.flush()
    return person


def _create_user(db, person=None, role="super_admin", suffix="st"):
    if not person:
        person = _create_person(db, suffix=suffix)
    user = User(
        person_id=person.id,
        email=person.email,
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _create_member(db, person, status="active"):
    mt = db.query(MembershipType).first()
    if not mt:
        mt = MembershipType(
            name="Standard",
            slug="standard",
            base_price=Decimal("100.00"),
            is_active=True,
        )
        db.add(mt)
        db.flush()
    member = Member(
        person_id=person.id,
        membership_type_id=mt.id,
        member_number=f"M-{person.id:04d}",
        status=status,
        joined_at=date(2026, 1, 1),
        is_active=True,
    )
    db.add(member)
    db.flush()
    return member


def _create_receipt(db, member, status="emitted"):
    _create_org(db)
    receipt = Receipt(
        receipt_number=f"FAC-2026-{member.id:04d}",
        member_id=member.id,
        origin="membership",
        description="Test membership fee",
        base_amount=Decimal("100.00"),
        vat_rate=Decimal("21.00"),
        vat_amount=Decimal("21.00"),
        total_amount=Decimal("121.00"),
        status=status,
        emission_date=date(2026, 4, 1),
        is_active=True,
    )
    db.add(receipt)
    db.flush()
    return receipt


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id, user.role)}


def _create_stripe_provider(db, status="active"):
    config = {
        "secret_key": "sk_test_abc123",
        "publishable_key": "pk_test_xyz456",
        "webhook_secret": "whsec_test789",
    }
    sensitive = ["secret_key", "webhook_secret"]
    encrypted = encrypt_config(config, sensitive)
    provider = PaymentProvider(
        provider_type="stripe",
        display_name="Stripe",
        status=status,
        config=encrypted,
        is_default=False,
    )
    db.add(provider)
    db.flush()
    return provider


# --- Checkout Endpoint ---


class TestStripeCheckout:
    @patch("app.domains.billing.providers.stripe_provider.StripeAdapter.create_payment")
    @patch("app.domains.billing.stripe_customer_service.stripe.StripeClient")
    def test_create_checkout_session(self, mock_client_cls, mock_create, client, db):
        _create_org(db)
        person = _create_person(db, suffix="chk1")
        user = _create_user(db, person=person, role="admin", suffix="chk1")
        member = _create_member(db, person)
        receipt = _create_receipt(db, member)
        _create_stripe_provider(db)

        # Mock Stripe customer creation
        mock_client = MagicMock()
        mock_client.v1.customers.create.return_value = MagicMock(id="cus_test123")
        mock_client_cls.return_value = mock_client

        mock_create.return_value = {
            "redirect_url": "https://checkout.stripe.com/session/cs_test",
            "session_id": "cs_test_session_001",
        }

        cookies = _auth_cookie(user)
        resp = client.post(
            f"/api/v1/receipts/{receipt.id}/stripe/checkout",
            cookies=cookies,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["redirect_url"] == "https://checkout.stripe.com/session/cs_test"
        assert data["session_id"] == "cs_test_session_001"

        # Verify session ID stored on receipt
        db.refresh(receipt)
        assert receipt.stripe_checkout_session_id == "cs_test_session_001"

    def test_checkout_receipt_not_found(self, client, db):
        user = _create_user(db, suffix="chk-nf")
        cookies = _auth_cookie(user)
        resp = client.post("/api/v1/receipts/99999/stripe/checkout", cookies=cookies)
        assert resp.status_code == 404

    def test_checkout_wrong_status(self, client, db):
        _create_org(db)
        person = _create_person(db, suffix="chk-ws")
        user = _create_user(db, person=person, role="admin", suffix="chk-ws")
        member = _create_member(db, person)
        receipt = _create_receipt(db, member, status="paid")
        _create_stripe_provider(db)

        cookies = _auth_cookie(user)
        resp = client.post(
            f"/api/v1/receipts/{receipt.id}/stripe/checkout",
            cookies=cookies,
        )
        assert resp.status_code == 400
        assert "not payable" in resp.json()["detail"]

    def test_checkout_no_stripe_provider(self, client, db):
        _create_org(db)
        person = _create_person(db, suffix="chk-np")
        user = _create_user(db, person=person, role="admin", suffix="chk-np")
        member = _create_member(db, person)
        receipt = _create_receipt(db, member)

        cookies = _auth_cookie(user)
        resp = client.post(
            f"/api/v1/receipts/{receipt.id}/stripe/checkout",
            cookies=cookies,
        )
        assert resp.status_code == 400
        assert "No active Stripe" in resp.json()["detail"]

    def test_member_can_pay_own_receipt(self, client, db):
        _create_org(db)
        person = _create_person(db, suffix="chk-own")
        user = _create_user(db, person=person, role="member", suffix="chk-own")
        member = _create_member(db, person)
        receipt = _create_receipt(db, member)
        _create_stripe_provider(db)

        with patch("app.domains.billing.providers.stripe_provider.StripeAdapter.create_payment") as mock_create, \
             patch("app.domains.billing.stripe_customer_service.stripe.StripeClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.v1.customers.create.return_value = MagicMock(id="cus_member_001")
            mock_client_cls.return_value = mock_client
            mock_create.return_value = {
                "redirect_url": "https://checkout.stripe.com/cs_test",
                "session_id": "cs_member_001",
            }
            cookies = _auth_cookie(user)
            resp = client.post(
                f"/api/v1/receipts/{receipt.id}/stripe/checkout",
                cookies=cookies,
            )
            assert resp.status_code == 200

    def test_member_cannot_pay_other_receipt(self, client, db):
        _create_org(db)
        person1 = _create_person(db, suffix="chk-oth1")
        person2 = _create_person(db, suffix="chk-oth2")
        _create_user(db, person=person1, role="member", suffix="chk-oth1")
        user2 = _create_user(db, person=person2, role="member", suffix="chk-oth2")
        member1 = _create_member(db, person1)
        receipt = _create_receipt(db, member1)
        _create_stripe_provider(db)

        cookies = _auth_cookie(user2)
        resp = client.post(
            f"/api/v1/receipts/{receipt.id}/stripe/checkout",
            cookies=cookies,
        )
        assert resp.status_code == 403


# --- Session Lookup ---


class TestStripeSessionLookup:
    def test_lookup_by_session_id(self, client, db):
        _create_org(db)
        person = _create_person(db, suffix="lkup1")
        user = _create_user(db, person=person, role="admin", suffix="lkup1")
        member = _create_member(db, person)
        receipt = _create_receipt(db, member)
        receipt.stripe_checkout_session_id = "cs_test_lookup_001"
        db.flush()

        cookies = _auth_cookie(user)
        resp = client.get(
            "/api/v1/receipts/by-stripe-session/cs_test_lookup_001",
            cookies=cookies,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["receipt_number"] == receipt.receipt_number

    def test_lookup_not_found(self, client, db):
        user = _create_user(db, suffix="lkup-nf")
        cookies = _auth_cookie(user)
        resp = client.get(
            "/api/v1/receipts/by-stripe-session/cs_nonexistent",
            cookies=cookies,
        )
        assert resp.status_code == 404


# --- Webhook → Receipt Status ---


class TestStripeWebhookFlow:
    """End-to-end: webhook POST → receipt status transition."""

    def test_checkout_completed_marks_receipt_paid(self, client, db):
        from app.api.v1.endpoints.webhooks import register_adapter, _ADAPTER_REGISTRY
        from app.domains.billing.providers.stripe_provider import StripeAdapter

        _create_org(db)
        person = _create_person(db, suffix="wh-paid")
        _create_user(db, person=person, suffix="wh-paid")
        member = _create_member(db, person)
        receipt = _create_receipt(db, member)
        _create_stripe_provider(db)

        # Build webhook payload
        payload = {
            "id": "evt_checkout_paid_001",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_001",
                    "metadata": {"receipt_id": str(receipt.id)},
                    "payment_intent": "pi_test_001",
                }
            },
        }

        # Patch verify_signature to bypass actual crypto
        with patch.object(StripeAdapter, "verify_signature", return_value=payload):
            resp = client.post(
                "/api/v1/webhooks/stripe",
                content=json.dumps(payload).encode(),
                headers={
                    "content-type": "application/json",
                    "stripe-signature": "t=123,v1=fake",
                },
            )
        assert resp.status_code == 200

        db.refresh(receipt)
        assert receipt.status == "paid"
        assert receipt.payment_method == "stripe_checkout"
        assert receipt.stripe_payment_intent_id == "pi_test_001"

    def test_checkout_expired_marks_receipt_returned(self, client, db):
        from app.domains.billing.providers.stripe_provider import StripeAdapter

        _create_org(db)
        person = _create_person(db, suffix="wh-exp")
        _create_user(db, person=person, suffix="wh-exp")
        member = _create_member(db, person)
        receipt = _create_receipt(db, member)
        _create_stripe_provider(db)

        payload = {
            "id": "evt_checkout_expired_001",
            "type": "checkout.session.expired",
            "data": {
                "object": {
                    "id": "cs_test_exp_001",
                    "metadata": {"receipt_id": str(receipt.id)},
                }
            },
        }

        with patch.object(StripeAdapter, "verify_signature", return_value=payload):
            resp = client.post(
                "/api/v1/webhooks/stripe",
                content=json.dumps(payload).encode(),
                headers={
                    "content-type": "application/json",
                    "stripe-signature": "t=123,v1=fake",
                },
            )
        assert resp.status_code == 200

        db.refresh(receipt)
        assert receipt.status == "returned"
        assert "expired" in receipt.return_reason.lower()

    def test_duplicate_webhook_no_double_process(self, client, db):
        from app.domains.billing.providers.stripe_provider import StripeAdapter

        _create_org(db)
        person = _create_person(db, suffix="wh-dup")
        _create_user(db, person=person, suffix="wh-dup")
        member = _create_member(db, person)
        receipt = _create_receipt(db, member)
        _create_stripe_provider(db)

        payload = {
            "id": "evt_dup_stripe_001",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_dup",
                    "metadata": {"receipt_id": str(receipt.id)},
                    "payment_intent": "pi_dup",
                }
            },
        }

        with patch.object(StripeAdapter, "verify_signature", return_value=payload):
            resp1 = client.post(
                "/api/v1/webhooks/stripe",
                content=json.dumps(payload).encode(),
                headers={
                    "content-type": "application/json",
                    "stripe-signature": "t=123,v1=fake",
                },
            )
            resp2 = client.post(
                "/api/v1/webhooks/stripe",
                content=json.dumps(payload).encode(),
                headers={
                    "content-type": "application/json",
                    "stripe-signature": "t=123,v1=fake",
                },
            )

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp2.json()["detail"] == "Duplicate event"

        # Only one event row
        count = (
            db.query(WebhookEvent)
            .filter(WebhookEvent.external_event_id == "evt_dup_stripe_001")
            .count()
        )
        assert count == 1
