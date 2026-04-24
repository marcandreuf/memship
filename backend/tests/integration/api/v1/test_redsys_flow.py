"""Integration tests for Redsys redirect flow — initiate endpoint + webhook dispatch."""

from datetime import date
from decimal import Decimal
from urllib.parse import urlencode

import pytest
from redsys.client import RedirectClient
from redsys.request import Request as _RedsysRequest
from redsys.response import Response as _RedsysResponse

from app.core.encryption import encrypt_config
from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.billing.models import (
    PaymentProvider,
    Receipt,
    WebhookEvent,
)
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


REDSYS_SECRET = "sq7HjrUOBfKmC576ILgskD5srU870gJ7"


@pytest.fixture(autouse=True)
def _reset_redsys_library_state():
    """python-redsys 1.2 stores ``_parameters`` on the class; reset for isolation."""
    _RedsysRequest._parameters = {}
    _RedsysResponse._parameters = {}
    yield
    _RedsysRequest._parameters = {}
    _RedsysResponse._parameters = {}


# --- helpers ---


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


def _create_person(db, suffix):
    person = Person(
        first_name="Redsys",
        last_name=f"Test-{suffix}",
        email=f"{suffix}@redsys-test.example",
    )
    db.add(person)
    db.flush()
    return person


def _create_user(db, person=None, role="super_admin", suffix="rs"):
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


def _create_member(db, person):
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
        status="active",
        joined_at=date(2026, 1, 1),
        is_active=True,
    )
    db.add(member)
    db.flush()
    return member


def _create_receipt(db, member, status="emitted", ds_order=None):
    _create_org(db)
    receipt = Receipt(
        receipt_number=f"FAC-2026-R{member.id:04d}",
        member_id=member.id,
        origin="membership",
        description="Test fee",
        base_amount=Decimal("100.00"),
        vat_rate=Decimal("21.00"),
        vat_amount=Decimal("21.00"),
        total_amount=Decimal("121.00"),
        status=status,
        emission_date=date(2026, 4, 1),
        is_active=True,
        redsys_ds_order=ds_order,
    )
    db.add(receipt)
    db.flush()
    return receipt


def _create_redsys_provider(db, status="active"):
    config = {
        "merchant_code": "100000001",
        "terminal_id": "1",
        "secret_key": REDSYS_SECRET,
        "environment": "test",
        "currency_code": "978",
    }
    encrypted = encrypt_config(config, ["secret_key"])
    provider = PaymentProvider(
        provider_type="redsys",
        display_name="Redsys",
        status=status,
        config=encrypted,
        is_default=False,
    )
    db.add(provider)
    db.flush()
    return provider


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id, user.role)}


def _sign_notification(
    *,
    ds_order,
    ds_response="0000",
    ds_auth_code="123456",
    ds_amount=12100,
    ds_currency=978,
    secret=REDSYS_SECRET,
):
    """Build a Ds_SignatureVersion / Ds_MerchantParameters / Ds_Signature envelope."""
    client = RedirectClient(secret)
    merchant_parameters = {
        "Ds_MerchantCode": "100000001",
        "Ds_Terminal": "1",
        "Ds_TransactionType": "0",
        "Ds_Currency": ds_currency,
        "Ds_Order": ds_order,
        "Ds_Amount": ds_amount,
        "Ds_Response": ds_response,
        "Ds_AuthorisationCode": ds_auth_code,
        "Ds_Date": "23%2F04%2F2026",
        "Ds_Hour": "10%3A00",
    }
    encoded = client.encode_parameters(merchant_parameters)
    signature = client.generate_signature(ds_order, encoded)
    return {
        "Ds_SignatureVersion": "HMAC_SHA256_V1",
        "Ds_MerchantParameters": encoded.decode(),
        "Ds_Signature": signature.decode(),
    }


def _post_webhook(client, envelope):
    return client.post(
        "/api/v1/webhooks/redsys",
        content=urlencode(envelope).encode(),
        headers={"content-type": "application/x-www-form-urlencoded"},
    )


# --- Initiate Endpoint ---


class TestRedsysInitiate:
    def test_admin_initiate_happy_path(self, client, db):
        _create_org(db)
        person = _create_person(db, suffix="ini-admin")
        user = _create_user(db, person=person, role="admin", suffix="ini-admin")
        member = _create_member(db, person)
        receipt = _create_receipt(db, member)
        _create_redsys_provider(db)

        resp = client.post(
            f"/api/v1/receipts/{receipt.id}/redsys/initiate",
            cookies=_auth_cookie(user),
            json={},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["redirect_url"].endswith("/sis/realizarPago")
        assert set(data["form_params"].keys()) == {
            "Ds_SignatureVersion",
            "Ds_MerchantParameters",
            "Ds_Signature",
        }
        assert data["form_params"]["Ds_SignatureVersion"] == "HMAC_SHA256_V1"
        assert data["ds_order"] == str(receipt.id).zfill(12)

        db.refresh(receipt)
        assert receipt.redsys_ds_order == data["ds_order"]

    def test_initiate_bizum_marks_method(self, client, db):
        _create_org(db)
        person = _create_person(db, suffix="ini-biz")
        user = _create_user(db, person=person, role="admin", suffix="ini-biz")
        member = _create_member(db, person)
        receipt = _create_receipt(db, member)
        _create_redsys_provider(db)

        resp = client.post(
            f"/api/v1/receipts/{receipt.id}/redsys/initiate",
            cookies=_auth_cookie(user),
            json={"method": "bizum"},
        )
        assert resp.status_code == 200
        db.refresh(receipt)
        assert receipt.payment_method == "bizum"
        assert receipt.redsys_ds_order is not None

    def test_initiate_receipt_not_found(self, client, db):
        user = _create_user(db, suffix="ini-404")
        resp = client.post(
            "/api/v1/receipts/99999/redsys/initiate",
            cookies=_auth_cookie(user),
            json={},
        )
        assert resp.status_code == 404

    def test_initiate_wrong_status_rejected(self, client, db):
        _create_org(db)
        person = _create_person(db, suffix="ini-ws")
        user = _create_user(db, person=person, role="admin", suffix="ini-ws")
        member = _create_member(db, person)
        receipt = _create_receipt(db, member, status="paid")
        _create_redsys_provider(db)

        resp = client.post(
            f"/api/v1/receipts/{receipt.id}/redsys/initiate",
            cookies=_auth_cookie(user),
            json={},
        )
        assert resp.status_code == 400
        assert "not payable" in resp.json()["detail"]

    def test_initiate_no_provider(self, client, db):
        _create_org(db)
        person = _create_person(db, suffix="ini-np")
        user = _create_user(db, person=person, role="admin", suffix="ini-np")
        member = _create_member(db, person)
        receipt = _create_receipt(db, member)

        resp = client.post(
            f"/api/v1/receipts/{receipt.id}/redsys/initiate",
            cookies=_auth_cookie(user),
            json={},
        )
        assert resp.status_code == 400
        assert "No active Redsys" in resp.json()["detail"]

    def test_initiate_member_cannot_pay_other(self, client, db):
        _create_org(db)
        p1 = _create_person(db, suffix="ini-o1")
        p2 = _create_person(db, suffix="ini-o2")
        _create_user(db, person=p1, role="member", suffix="ini-o1")
        user2 = _create_user(db, person=p2, role="member", suffix="ini-o2")
        member1 = _create_member(db, p1)
        receipt = _create_receipt(db, member1)
        _create_redsys_provider(db)

        resp = client.post(
            f"/api/v1/receipts/{receipt.id}/redsys/initiate",
            cookies=_auth_cookie(user2),
            json={},
        )
        assert resp.status_code == 403


# --- Return status endpoint ---


class TestRedsysReturnStatus:
    def test_admin_reads_status(self, client, db):
        _create_org(db)
        person = _create_person(db, suffix="ret-1")
        user = _create_user(db, person=person, role="admin", suffix="ret-1")
        member = _create_member(db, person)
        receipt = _create_receipt(db, member, ds_order="000000000501")

        resp = client.get(
            f"/api/v1/receipts/{receipt.id}/redsys/return",
            cookies=_auth_cookie(user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["receipt_id"] == receipt.id
        assert data["ds_order"] == "000000000501"
        assert data["status"] == "emitted"
        assert "notification" in data["authoritative_note"].lower()


# --- Webhook → Receipt Status ---


class TestRedsysWebhookFlow:
    def test_paid_notification_marks_receipt_paid(self, client, db):
        _create_org(db)
        person = _create_person(db, suffix="wh-paid")
        _create_user(db, person=person, suffix="wh-paid")
        member = _create_member(db, person)
        receipt = _create_receipt(db, member, ds_order="000000001001")
        _create_redsys_provider(db)

        envelope = _sign_notification(
            ds_order=receipt.redsys_ds_order,
            ds_response="0000",
            ds_auth_code="AUTH777",
        )
        resp = _post_webhook(client, envelope)
        assert resp.status_code == 200, resp.text

        db.expire_all()
        receipt = db.query(Receipt).filter(Receipt.id == receipt.id).first()
        assert receipt.status == "paid"
        assert receipt.payment_method == "redsys"
        assert receipt.payment_date == date.today()
        assert receipt.redsys_auth_code == "AUTH777"
        assert receipt.transaction_id == "AUTH777"

    def test_bizum_payment_method_preserved(self, client, db):
        _create_org(db)
        person = _create_person(db, suffix="wh-biz")
        _create_user(db, person=person, suffix="wh-biz")
        member = _create_member(db, person)
        receipt = _create_receipt(db, member, ds_order="000000001501")
        receipt.payment_method = "bizum"  # set by initiate when method=bizum
        db.flush()
        _create_redsys_provider(db)

        envelope = _sign_notification(
            ds_order=receipt.redsys_ds_order, ds_response="0000"
        )
        resp = _post_webhook(client, envelope)
        assert resp.status_code == 200

        db.expire_all()
        receipt = db.query(Receipt).filter(Receipt.id == receipt.id).first()
        assert receipt.status == "paid"
        assert receipt.payment_method == "bizum"

    def test_denied_notification_leaves_receipt_unchanged(self, client, db):
        _create_org(db)
        person = _create_person(db, suffix="wh-den")
        _create_user(db, person=person, suffix="wh-den")
        member = _create_member(db, person)
        receipt = _create_receipt(db, member, ds_order="000000002001")
        _create_redsys_provider(db)

        envelope = _sign_notification(
            ds_order=receipt.redsys_ds_order, ds_response="0180"
        )
        resp = _post_webhook(client, envelope)
        assert resp.status_code == 200

        db.expire_all()
        receipt = db.query(Receipt).filter(Receipt.id == receipt.id).first()
        assert receipt.status == "emitted"
        assert receipt.payment_method is None
        assert receipt.redsys_auth_code is None

        event = (
            db.query(WebhookEvent)
            .filter(WebhookEvent.provider_type == "redsys")
            .order_by(WebhookEvent.id.desc())
            .first()
        )
        assert event.status == "ignored"
        assert "denied" in (event.error_message or "").lower()

    def test_tampered_signature_rejected(self, client, db):
        _create_org(db)
        person = _create_person(db, suffix="wh-bad")
        _create_user(db, person=person, suffix="wh-bad")
        member = _create_member(db, person)
        receipt = _create_receipt(db, member, ds_order="000000002501")
        _create_redsys_provider(db)

        envelope = _sign_notification(ds_order=receipt.redsys_ds_order)
        # Tamper: flip the signature
        envelope["Ds_Signature"] = "x" * len(envelope["Ds_Signature"])
        resp = _post_webhook(client, envelope)
        assert resp.status_code == 400
        assert "ignature" in resp.json()["detail"]

        db.expire_all()
        receipt = db.query(Receipt).filter(Receipt.id == receipt.id).first()
        assert receipt.status == "emitted"

    def test_duplicate_notification_no_double_process(self, client, db):
        _create_org(db)
        person = _create_person(db, suffix="wh-dup")
        _create_user(db, person=person, suffix="wh-dup")
        member = _create_member(db, person)
        receipt = _create_receipt(db, member, ds_order="000000003001")
        _create_redsys_provider(db)

        envelope = _sign_notification(
            ds_order=receipt.redsys_ds_order, ds_response="0000"
        )
        r1 = _post_webhook(client, envelope)
        r2 = _post_webhook(client, envelope)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r2.json()["detail"] == "Duplicate event"

        count = (
            db.query(WebhookEvent)
            .filter(WebhookEvent.provider_type == "redsys")
            .count()
        )
        assert count == 1

    def test_unknown_order_ignored(self, client, db):
        _create_org(db)
        _create_redsys_provider(db)

        envelope = _sign_notification(ds_order="000000999999", ds_response="0000")
        resp = _post_webhook(client, envelope)
        assert resp.status_code == 200

        event = (
            db.query(WebhookEvent)
            .filter(WebhookEvent.provider_type == "redsys")
            .order_by(WebhookEvent.id.desc())
            .first()
        )
        assert event is not None
        assert event.status == "ignored"
        assert "no receipt" in (event.error_message or "").lower()

    def test_webhook_requires_active_provider(self, client, db):
        """Without any Redsys provider row, dispatch returns 404."""
        envelope = _sign_notification(ds_order="000000999998", ds_response="0000")
        resp = _post_webhook(client, envelope)
        assert resp.status_code == 404
