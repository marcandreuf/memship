"""Integration tests for payment provider management endpoints."""

from app.core.encryption import decrypt_config
from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.billing.models import PaymentProvider
from app.domains.billing.provider_config import get_sensitive_fields
from app.domains.persons.models import Person


def _create_user(db, role="super_admin", suffix="pp"):
    person = Person(first_name="Test", last_name="User", email=f"{suffix}-{role}@test.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=f"{suffix}-{role}@test.com",
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id, user.role)}


def _create_provider(db, provider_type="stripe", status="disabled", config=None):
    """Create a payment provider directly in the DB (no encryption)."""
    if config is None:
        config = {}
    provider = PaymentProvider(
        provider_type=provider_type,
        display_name=provider_type.replace("_", " ").title(),
        status=status,
        config=config,
        is_default=False,
    )
    db.add(provider)
    db.flush()
    return provider


# --- Authorization ---


class TestAuthorization:
    def test_admin_cannot_access(self, client, db):
        admin = _create_user(db, role="admin", suffix="pp-auth1")
        cookies = _auth_cookie(admin)
        resp = client.get("/api/v1/payment-providers/", cookies=cookies)
        assert resp.status_code == 403

    def test_member_cannot_access(self, client, db):
        member = _create_user(db, role="member", suffix="pp-auth2")
        cookies = _auth_cookie(member)
        resp = client.get("/api/v1/payment-providers/", cookies=cookies)
        assert resp.status_code == 403

    def test_unauthenticated_cannot_access(self, client):
        resp = client.get("/api/v1/payment-providers/")
        assert resp.status_code == 401

    def test_super_admin_can_access(self, client, db):
        user = _create_user(db, suffix="pp-auth3")
        cookies = _auth_cookie(user)
        resp = client.get("/api/v1/payment-providers/", cookies=cookies)
        assert resp.status_code == 200


# --- List ---


class TestListProviders:
    def test_list_empty(self, client, db):
        user = _create_user(db, suffix="pp-list1")
        cookies = _auth_cookie(user)
        resp = client.get("/api/v1/payment-providers/", cookies=cookies)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []

    def test_list_returns_providers(self, client, db):
        user = _create_user(db, suffix="pp-list2")
        _create_provider(db, provider_type="sepa_direct_debit", config={"format": "pain.008.001.02"})
        cookies = _auth_cookie(user)
        resp = client.get("/api/v1/payment-providers/", cookies=cookies)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["provider_type"] == "sepa_direct_debit"


# --- Create ---


class TestCreateProvider:
    def test_create_stripe_provider(self, client, db):
        user = _create_user(db, suffix="pp-create1")
        cookies = _auth_cookie(user)
        payload = {
            "provider_type": "stripe",
            "display_name": "Stripe",
            "status": "disabled",
            "config": {
                "secret_key": "sk_test_abc123",
                "publishable_key": "pk_test_xyz456",
                "webhook_secret": "",
                "mode": "webhook",
            },
        }
        resp = client.post("/api/v1/payment-providers/", json=payload, cookies=cookies)
        assert resp.status_code == 201
        data = resp.json()
        assert data["provider_type"] == "stripe"
        assert data["display_name"] == "Stripe"
        # Config should be masked
        assert data["config"]["secret_key"] == "****c123"
        assert data["config"]["publishable_key"] == "pk_test_xyz456"  # not sensitive

    def test_create_encrypts_sensitive_fields(self, client, db):
        user = _create_user(db, suffix="pp-create2")
        cookies = _auth_cookie(user)
        payload = {
            "provider_type": "stripe",
            "display_name": "Stripe",
            "config": {
                "secret_key": "sk_test_abc123",
                "publishable_key": "pk_test_xyz456",
                "mode": "webhook",
            },
        }
        resp = client.post("/api/v1/payment-providers/", json=payload, cookies=cookies)
        assert resp.status_code == 201

        # Check DB: sensitive fields should be encrypted
        provider = db.query(PaymentProvider).filter(
            PaymentProvider.provider_type == "stripe"
        ).first()
        assert provider.config["secret_key"] != "sk_test_abc123"
        # But decrypting should restore original
        sensitive = get_sensitive_fields("stripe")
        decrypted = decrypt_config(provider.config, sensitive)
        assert decrypted["secret_key"] == "sk_test_abc123"

    def test_create_duplicate_type_rejected(self, client, db):
        user = _create_user(db, suffix="pp-create3")
        _create_provider(db, provider_type="stripe")
        cookies = _auth_cookie(user)
        payload = {
            "provider_type": "stripe",
            "display_name": "Stripe 2",
            "config": {},
        }
        resp = client.post("/api/v1/payment-providers/", json=payload, cookies=cookies)
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"]

    def test_create_unknown_type_rejected(self, client, db):
        user = _create_user(db, suffix="pp-create4")
        cookies = _auth_cookie(user)
        payload = {
            "provider_type": "unknown_provider",
            "display_name": "Unknown",
            "config": {},
        }
        resp = client.post("/api/v1/payment-providers/", json=payload, cookies=cookies)
        assert resp.status_code == 400
        assert "Unknown provider type" in resp.json()["detail"]

    def test_create_sepa_provider(self, client, db):
        user = _create_user(db, suffix="pp-create5")
        cookies = _auth_cookie(user)
        payload = {
            "provider_type": "sepa_direct_debit",
            "display_name": "SEPA Direct Debit",
            "status": "active",
            "config": {"format": "pain.008.001.02"},
            "is_default": True,
        }
        resp = client.post("/api/v1/payment-providers/", json=payload, cookies=cookies)
        assert resp.status_code == 201
        data = resp.json()
        assert data["is_default"] is True
        # SEPA has no sensitive fields, so config is unchanged
        assert data["config"]["format"] == "pain.008.001.02"


# --- Get Detail ---


class TestGetProvider:
    def test_get_existing(self, client, db):
        user = _create_user(db, suffix="pp-get1")
        provider = _create_provider(
            db, provider_type="sepa_direct_debit",
            config={"format": "pain.008.001.02"},
        )
        cookies = _auth_cookie(user)
        resp = client.get(f"/api/v1/payment-providers/{provider.id}", cookies=cookies)
        assert resp.status_code == 200
        assert resp.json()["provider_type"] == "sepa_direct_debit"

    def test_get_not_found(self, client, db):
        user = _create_user(db, suffix="pp-get2")
        cookies = _auth_cookie(user)
        resp = client.get("/api/v1/payment-providers/99999", cookies=cookies)
        assert resp.status_code == 404


# --- Update ---


class TestUpdateProvider:
    def test_update_display_name(self, client, db):
        user = _create_user(db, suffix="pp-upd1")
        provider = _create_provider(db, provider_type="sepa_direct_debit")
        cookies = _auth_cookie(user)
        resp = client.put(
            f"/api/v1/payment-providers/{provider.id}",
            json={"display_name": "SEPA Renamed"},
            cookies=cookies,
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "SEPA Renamed"

    def test_update_config_re_encrypts(self, client, db):
        user = _create_user(db, suffix="pp-upd2")
        cookies = _auth_cookie(user)
        # Create via API so it's encrypted
        create_resp = client.post(
            "/api/v1/payment-providers/",
            json={
                "provider_type": "stripe",
                "display_name": "Stripe",
                "config": {
                    "secret_key": "sk_test_original",
                    "publishable_key": "pk_test_xyz",
                    "mode": "webhook",
                },
            },
            cookies=cookies,
        )
        provider_id = create_resp.json()["id"]

        # Update with new secret_key
        resp = client.put(
            f"/api/v1/payment-providers/{provider_id}",
            json={
                "config": {
                    "secret_key": "sk_test_updated",
                    "publishable_key": "pk_test_xyz",
                    "mode": "webhook",
                },
            },
            cookies=cookies,
        )
        assert resp.status_code == 200
        assert resp.json()["config"]["secret_key"] == "****ated"

        # Verify in DB
        provider = db.query(PaymentProvider).filter(
            PaymentProvider.id == provider_id
        ).first()
        sensitive = get_sensitive_fields("stripe")
        decrypted = decrypt_config(provider.config, sensitive)
        assert decrypted["secret_key"] == "sk_test_updated"

    def test_update_masked_value_keeps_existing(self, client, db):
        user = _create_user(db, suffix="pp-upd3")
        cookies = _auth_cookie(user)
        # Create via API
        create_resp = client.post(
            "/api/v1/payment-providers/",
            json={
                "provider_type": "paypal",
                "display_name": "PayPal",
                "config": {
                    "client_id": "pp_client",
                    "client_secret": "pp_secret_original",
                    "environment": "sandbox",
                },
            },
            cookies=cookies,
        )
        provider_id = create_resp.json()["id"]

        # Update sending masked value back — should keep original
        resp = client.put(
            f"/api/v1/payment-providers/{provider_id}",
            json={
                "config": {
                    "client_id": "pp_client_new",
                    "client_secret": "****inal",  # masked value
                    "environment": "sandbox",
                },
            },
            cookies=cookies,
        )
        assert resp.status_code == 200

        # Verify original secret is preserved
        provider = db.query(PaymentProvider).filter(
            PaymentProvider.id == provider_id
        ).first()
        sensitive = get_sensitive_fields("paypal")
        decrypted = decrypt_config(provider.config, sensitive)
        assert decrypted["client_secret"] == "pp_secret_original"

    def test_update_not_found(self, client, db):
        user = _create_user(db, suffix="pp-upd4")
        cookies = _auth_cookie(user)
        resp = client.put(
            "/api/v1/payment-providers/99999",
            json={"display_name": "Nope"},
            cookies=cookies,
        )
        assert resp.status_code == 404


# --- Delete ---


class TestDeleteProvider:
    def test_delete_provider(self, client, db):
        user = _create_user(db, suffix="pp-del1")
        provider = _create_provider(db, provider_type="stripe")
        cookies = _auth_cookie(user)
        resp = client.delete(
            f"/api/v1/payment-providers/{provider.id}", cookies=cookies
        )
        assert resp.status_code == 204

        # Verify deleted
        assert db.query(PaymentProvider).filter(
            PaymentProvider.id == provider.id
        ).first() is None

    def test_delete_not_found(self, client, db):
        user = _create_user(db, suffix="pp-del2")
        cookies = _auth_cookie(user)
        resp = client.delete("/api/v1/payment-providers/99999", cookies=cookies)
        assert resp.status_code == 404


# --- Toggle ---


class TestToggleProvider:
    def test_toggle_active_to_disabled(self, client, db):
        user = _create_user(db, suffix="pp-tog1")
        provider = _create_provider(db, provider_type="sepa_direct_debit", status="active")
        cookies = _auth_cookie(user)
        resp = client.post(
            f"/api/v1/payment-providers/{provider.id}/toggle", cookies=cookies
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"

    def test_toggle_disabled_to_active(self, client, db):
        user = _create_user(db, suffix="pp-tog2")
        provider = _create_provider(db, provider_type="stripe", status="disabled")
        cookies = _auth_cookie(user)
        resp = client.post(
            f"/api/v1/payment-providers/{provider.id}/toggle", cookies=cookies
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_toggle_test_to_active(self, client, db):
        user = _create_user(db, suffix="pp-tog3")
        provider = _create_provider(db, provider_type="redsys", status="test")
        cookies = _auth_cookie(user)
        resp = client.post(
            f"/api/v1/payment-providers/{provider.id}/toggle", cookies=cookies
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_toggle_not_found(self, client, db):
        user = _create_user(db, suffix="pp-tog4")
        cookies = _auth_cookie(user)
        resp = client.post(
            "/api/v1/payment-providers/99999/toggle", cookies=cookies
        )
        assert resp.status_code == 404


# --- Test Connection ---


class TestTestProvider:
    def test_valid_stripe_config(self, client, db):
        user = _create_user(db, suffix="pp-test1")
        cookies = _auth_cookie(user)
        # Create with valid config via API
        create_resp = client.post(
            "/api/v1/payment-providers/",
            json={
                "provider_type": "stripe",
                "display_name": "Stripe",
                "config": {
                    "secret_key": "sk_test_abc123",
                    "publishable_key": "pk_test_xyz456",
                    "mode": "webhook",
                },
            },
            cookies=cookies,
        )
        provider_id = create_resp.json()["id"]

        resp = client.post(
            f"/api/v1/payment-providers/{provider_id}/test", cookies=cookies
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_invalid_stripe_config(self, client, db):
        user = _create_user(db, suffix="pp-test2")
        cookies = _auth_cookie(user)
        create_resp = client.post(
            "/api/v1/payment-providers/",
            json={
                "provider_type": "stripe",
                "display_name": "Stripe",
                "config": {
                    "secret_key": "invalid_key",
                    "publishable_key": "pk_test_xyz",
                    "mode": "webhook",
                },
            },
            cookies=cookies,
        )
        provider_id = create_resp.json()["id"]

        resp = client.post(
            f"/api/v1/payment-providers/{provider_id}/test", cookies=cookies
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "sk_" in data["message"]

    def test_sepa_config_valid(self, client, db):
        user = _create_user(db, suffix="pp-test3")
        cookies = _auth_cookie(user)
        create_resp = client.post(
            "/api/v1/payment-providers/",
            json={
                "provider_type": "sepa_direct_debit",
                "display_name": "SEPA",
                "config": {"format": "pain.008.001.02"},
            },
            cookies=cookies,
        )
        provider_id = create_resp.json()["id"]

        resp = client.post(
            f"/api/v1/payment-providers/{provider_id}/test", cookies=cookies
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_not_found(self, client, db):
        user = _create_user(db, suffix="pp-test4")
        cookies = _auth_cookie(user)
        resp = client.post(
            "/api/v1/payment-providers/99999/test", cookies=cookies
        )
        assert resp.status_code == 404


# --- Types ---


class TestProviderTypes:
    def test_list_types(self, client, db):
        user = _create_user(db, suffix="pp-types1")
        cookies = _auth_cookie(user)
        resp = client.get("/api/v1/payment-providers/types", cookies=cookies)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5
        types = {t["provider_type"] for t in data}
        assert types == {"sepa_direct_debit", "stripe", "redsys", "goCardless", "paypal"}

    def test_sepa_is_available(self, client, db):
        user = _create_user(db, suffix="pp-types2")
        cookies = _auth_cookie(user)
        resp = client.get("/api/v1/payment-providers/types", cookies=cookies)
        data = resp.json()
        sepa = next(t for t in data if t["provider_type"] == "sepa_direct_debit")
        assert sepa["available"] is True

    def test_stripe_is_coming_soon(self, client, db):
        user = _create_user(db, suffix="pp-types3")
        cookies = _auth_cookie(user)
        resp = client.get("/api/v1/payment-providers/types", cookies=cookies)
        data = resp.json()
        stripe = next(t for t in data if t["provider_type"] == "stripe")
        assert stripe["available"] is False

    def test_types_include_fields(self, client, db):
        user = _create_user(db, suffix="pp-types4")
        cookies = _auth_cookie(user)
        resp = client.get("/api/v1/payment-providers/types", cookies=cookies)
        data = resp.json()
        stripe = next(t for t in data if t["provider_type"] == "stripe")
        assert len(stripe["fields"]) == 4
        assert stripe["sensitive_fields"] == ["secret_key", "webhook_secret"]
