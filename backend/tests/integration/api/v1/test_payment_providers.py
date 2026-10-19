"""Integration tests for payment provider management endpoints."""

from app.core.encryption import decrypt_config
from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.billing.models import PaymentProvider
from app.domains.billing.provider_config import get_sensitive_fields
from app.domains.persons.models import Person


def _create_user(db, role="super_admin", suffix="pp"):
    person = Person(first_name="Test", last_name="User", email=f"{suffix}-{role}@examplee6e3b1.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=f"{suffix}-{role}@examplee6e3b1.com",
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id)}


# A complete config per type. Activation validates (#218), so a provider built
# for a test that switches it on needs one; pass `config={}` to build a provider
# that is deliberately not ready.
VALID_CONFIGS = {
    "stripe": {
        "secret_key": "sk_test_abc123",
        "publishable_key": "pk_test_xyz456",
        "webhook_secret": "whsec_test789",
    },
    "redsys": {
        "merchant_code": "100000001",
        "terminal_id": "1",
        "secret_key": "sq7HjrUOBfKmC576ILgskD5srU870gJ7",
        "environment": "test",
        "currency_code": "978",
    },
    "sepa_direct_debit": {"format": "pain.008.001.02"},
}


def _create_provider(db, provider_type="stripe", status="disabled", config=None):
    """Create a payment provider directly in the DB (no encryption)."""
    if config is None:
        config = dict(VALID_CONFIGS.get(provider_type, {}))
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


# --- Active methods (member-accessible) ---


class TestActiveMethods:
    url = "/api/v1/payment-providers/active-methods"

    def test_unauthenticated_rejected(self, client):
        resp = client.get(self.url)
        assert resp.status_code == 401

    def test_member_can_list_active_types(self, client, db):
        _create_provider(db, provider_type="stripe", status="active")
        _create_provider(db, provider_type="redsys", status="test")
        _create_provider(db, provider_type="sepa_direct_debit", status="disabled")
        member = _create_user(db, role="member", suffix="pp-act1")

        resp = client.get(self.url, cookies=_auth_cookie(member))
        assert resp.status_code == 200
        data = resp.json()
        types = {row["provider_type"] for row in data}
        assert types == {"stripe", "redsys"}
        # Disabled providers omitted; no config leaked. `methods` is derived from
        # the config but is not part of it — it names payment methods, never a
        # credential or a setting.
        assert all(
            set(row.keys()) == {"provider_type", "status", "methods"} for row in data
        )

    def test_empty_when_no_active_providers(self, client, db):
        _create_provider(db, provider_type="stripe", status="disabled")
        member = _create_user(db, role="member", suffix="pp-act2")
        resp = client.get(self.url, cookies=_auth_cookie(member))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_redsys_does_not_offer_bizum_until_it_is_switched_on(self, client, db):
        """A Redsys config saved before the switch existed has no key for it, and
        the member must not be shown a Bizum button the bank may refuse (#405)."""
        _create_provider(db, provider_type="redsys", status="active")
        member = _create_user(db, role="member", suffix="pp-act3")

        resp = client.get(self.url, cookies=_auth_cookie(member))

        row = next(r for r in resp.json() if r["provider_type"] == "redsys")
        assert row["methods"] == ["card"]

    def test_redsys_offers_bizum_once_the_switch_is_on(self, client, db):
        _create_provider(
            db,
            provider_type="redsys",
            status="active",
            config={**VALID_CONFIGS["redsys"], "enable_bizum": "true"},
        )
        member = _create_user(db, role="member", suffix="pp-act4")

        resp = client.get(self.url, cookies=_auth_cookie(member))

        row = next(r for r in resp.json() if r["provider_type"] == "redsys")
        assert row["methods"] == ["card", "bizum"]


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

    def test_list_honours_per_page(self, client, db):
        # The route took `page_size`, a name nothing sends (#255).
        user = _create_user(db, suffix="pp-list3")
        _create_provider(db, provider_type="stripe")
        _create_provider(db, provider_type="sepa_direct_debit", config={"format": "pain.008.001.02"})
        resp = client.get("/api/v1/payment-providers/?page=1&per_page=1", cookies=_auth_cookie(user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["meta"]["per_page"] == 1
        assert data["meta"]["total"] == 2


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
                "webhook_secret": "whsec_test789",
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
                "webhook_secret": "whsec_test789",
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
                    "webhook_secret": "whsec_test789",
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
                    "webhook_secret": "whsec_test789",
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
        # Create via API. Uses `stripe` rather than `paypal`: an adapterless
        # type is refused at create now (#340), and the behaviour under test
        # here — a masked value sent back means "unchanged" — has nothing to do
        # with which provider it is.
        create_resp = client.post(
            "/api/v1/payment-providers/",
            json={
                "provider_type": "stripe",
                "display_name": "Stripe",
                "config": {
                    "publishable_key": "pk_test_original",
                    "secret_key": "sk_test_original",
                    "webhook_secret": "whsec_original",
                },
            },
            cookies=cookies,
        )
        assert create_resp.status_code == 201, create_resp.text
        provider_id = create_resp.json()["id"]

        # Update sending masked value back — should keep original
        resp = client.put(
            f"/api/v1/payment-providers/{provider_id}",
            json={
                "config": {
                    "publishable_key": "pk_test_new",
                    "secret_key": "****inal",  # masked value
                    "webhook_secret": "whsec_original",
                },
            },
            cookies=cookies,
        )
        assert resp.status_code == 200, resp.text

        # Verify original secret is preserved
        provider = db.query(PaymentProvider).filter(
            PaymentProvider.id == provider_id
        ).first()
        sensitive = get_sensitive_fields("stripe")
        decrypted = decrypt_config(provider.config, sensitive)
        assert decrypted["secret_key"] == "sk_test_original"

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


# --- Activation guard (#218) -----------------------------------------------


class TestActivationRequiresCompleteConfig:
    """A provider reaches members the moment it is active, so activation is the
    last point where an incomplete config is still a settings problem."""

    def test_toggle_on_rejected_when_config_incomplete(self, client, db):
        user = _create_user(db, suffix="pp-guard1")
        provider = _create_provider(db, provider_type="stripe", status="disabled", config={})
        cookies = _auth_cookie(user)

        resp = client.post(
            f"/api/v1/payment-providers/{provider.id}/toggle", cookies=cookies
        )

        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert detail["code"] == "provider_not_ready"
        # The missing fields are named, so the administrator knows what to fill.
        assert {"code": "missing_required_field", "field": "secret_key"} in detail["errors"]

    def test_rejected_provider_stays_disabled(self, client, db):
        user = _create_user(db, suffix="pp-guard2")
        provider = _create_provider(db, provider_type="stripe", status="disabled", config={})
        cookies = _auth_cookie(user)

        client.post(f"/api/v1/payment-providers/{provider.id}/toggle", cookies=cookies)

        db.refresh(provider)
        assert provider.status == "disabled"

    def test_incomplete_provider_is_not_advertised_to_members(self, client, db):
        """The whole point of the guard: `/active-methods` drives the member's
        pay buttons, and a refused activation must not reach it."""
        user = _create_user(db, suffix="pp-guard3")
        member = _create_user(db, role="member", suffix="pp-guard3m")
        provider = _create_provider(db, provider_type="stripe", status="disabled", config={})

        client.post(
            f"/api/v1/payment-providers/{provider.id}/toggle", cookies=_auth_cookie(user)
        )

        resp = client.get(
            "/api/v1/payment-providers/active-methods", cookies=_auth_cookie(member)
        )
        assert resp.status_code == 200
        assert "stripe" not in [m["provider_type"] for m in resp.json()]

    def test_toggle_off_always_allowed(self, client, db):
        """Switching a provider off must never be blocked by its own config —
        that is the escape hatch when credentials go bad."""
        user = _create_user(db, suffix="pp-guard4")
        provider = _create_provider(db, provider_type="stripe", status="active", config={})
        cookies = _auth_cookie(user)

        resp = client.post(
            f"/api/v1/payment-providers/{provider.id}/toggle", cookies=cookies
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"

    def test_create_active_rejected_when_config_incomplete(self, client, db):
        user = _create_user(db, suffix="pp-guard5")
        cookies = _auth_cookie(user)

        resp = client.post(
            "/api/v1/payment-providers/",
            json={
                "provider_type": "stripe",
                "display_name": "Stripe",
                "status": "active",
                "config": {"secret_key": "sk_test_abc123"},
            },
            cookies=cookies,
        )

        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "provider_not_ready"
        assert db.query(PaymentProvider).filter_by(provider_type="stripe").count() == 0

    def test_create_disabled_allowed_when_config_incomplete(self, client, db):
        """Saving a half-filled provider is how it gets configured — only
        switching it on is guarded."""
        user = _create_user(db, suffix="pp-guard6")
        cookies = _auth_cookie(user)

        resp = client.post(
            "/api/v1/payment-providers/",
            json={
                "provider_type": "stripe",
                "display_name": "Stripe",
                "status": "disabled",
                "config": {"secret_key": "sk_test_abc123"},
            },
            cookies=cookies,
        )

        assert resp.status_code == 201

    def test_update_cannot_empty_a_required_field_on_a_live_provider(self, client, db):
        user = _create_user(db, suffix="pp-guard7")
        provider = _create_provider(db, provider_type="redsys", status="active")
        cookies = _auth_cookie(user)

        resp = client.put(
            f"/api/v1/payment-providers/{provider.id}",
            json={"config": {**VALID_CONFIGS["redsys"], "merchant_code": ""}},
            cookies=cookies,
        )

        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "provider_not_ready"
        db.refresh(provider)
        assert provider.config["merchant_code"] == "100000001"

    def test_update_may_activate_and_complete_the_config_together(self, client, db):
        """Validated against the merged result, not the payload alone."""
        user = _create_user(db, suffix="pp-guard8")
        provider = _create_provider(db, provider_type="stripe", status="disabled", config={})
        cookies = _auth_cookie(user)

        resp = client.put(
            f"/api/v1/payment-providers/{provider.id}",
            json={"status": "active", "config": VALID_CONFIGS["stripe"]},
            cookies=cookies,
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_malformed_key_rejected_not_just_missing_ones(self, client, db):
        user = _create_user(db, suffix="pp-guard9")
        provider = _create_provider(
            db,
            provider_type="stripe",
            status="disabled",
            config={**VALID_CONFIGS["stripe"], "secret_key": "not-a-stripe-key"},
        )
        cookies = _auth_cookie(user)

        resp = client.post(
            f"/api/v1/payment-providers/{provider.id}/toggle", cookies=cookies
        )

        assert resp.status_code == 400
        assert {
            "code": "must_start_with",
            "field": "secret_key",
            "prefix": "sk_",
        } in resp.json()["detail"]["errors"]


class TestMalformedValuesAreRefusedOnSave:
    """A disabled provider used to store anything at all.

    Format validation ran only through `_require_ready`, which fires when a
    provider becomes member-facing — so a typo sat encrypted in the row until
    activation, and a webhook secret's typo was never caught at all, because
    nothing local can tell a wrong signing secret from a right one.
    """

    def test_a_disabled_provider_refuses_a_malformed_secret_key(self, client, db):
        user = _create_user(db, suffix="pp-fmt1")

        resp = client.post(
            "/api/v1/payment-providers/",
            json={
                "provider_type": "stripe",
                "display_name": "Stripe",
                "status": "disabled",
                "config": {"secret_key": "foo"},
            },
            cookies=_auth_cookie(user),
        )

        assert resp.status_code == 400
        assert {
            "code": "must_start_with",
            "field": "secret_key",
            "prefix": "sk_",
        } in resp.json()["detail"]["errors"]

    def test_a_disabled_provider_refuses_a_malformed_webhook_secret(self, client, db):
        user = _create_user(db, suffix="pp-fmt2")
        provider = _create_provider(db, provider_type="stripe", status="disabled", config={})

        resp = client.put(
            f"/api/v1/payment-providers/{provider.id}",
            json={"config": {"webhook_secret": "nonsense"}},
            cookies=_auth_cookie(user),
        )

        assert resp.status_code == 400
        assert {
            "code": "must_start_with",
            "field": "webhook_secret",
            "prefix": "whsec_",
        } in resp.json()["detail"]["errors"]

    def test_a_partial_config_is_still_savable(self, client, db):
        """The point of the split: missing is fine while it is switched off."""
        user = _create_user(db, suffix="pp-fmt3")

        resp = client.post(
            "/api/v1/payment-providers/",
            json={
                "provider_type": "stripe",
                "display_name": "Stripe",
                "status": "disabled",
                "config": {"secret_key": "sk_test_abc"},
            },
            cookies=_auth_cookie(user),
        )

        assert resp.status_code == 201, resp.json()

    def test_activation_still_demands_the_whole_set(self, client, db):
        user = _create_user(db, suffix="pp-fmt4")

        resp = client.post(
            "/api/v1/payment-providers/",
            json={
                "provider_type": "stripe",
                "display_name": "Stripe",
                "status": "active",
                "config": {"secret_key": "sk_test_abc"},
            },
            cookies=_auth_cookie(user),
        )

        assert resp.status_code == 400
        codes = {e["code"] for e in resp.json()["detail"]["errors"]}
        assert "missing_required_field" in codes


class TestAStoredSecretCannotBeErased:
    """Blanking a sensitive field used to store the empty string over it.

    The stored value is encrypted, so overwriting it with nothing destroyed the
    only copy — and on a disabled row it answered 200, because the presence
    check runs only for member-facing providers. The form sends `****` for a
    field the administrator did not touch, so an empty one is a lost paste
    rather than an instruction (#406).
    """

    def _create_stripe(self, client, cookies, status="disabled"):
        resp = client.post(
            "/api/v1/payment-providers/",
            json={
                "provider_type": "stripe",
                "display_name": "Stripe",
                "status": status,
                "config": VALID_CONFIGS["stripe"],
            },
            cookies=cookies,
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["id"]

    def test_blanking_a_secret_on_a_disabled_provider_is_refused(self, client, db):
        user = _create_user(db, suffix="pp-clr1")
        cookies = _auth_cookie(user)
        provider_id = self._create_stripe(client, cookies)

        resp = client.put(
            f"/api/v1/payment-providers/{provider_id}",
            json={"config": {**VALID_CONFIGS["stripe"], "secret_key": ""}},
            cookies=cookies,
        )

        assert resp.status_code == 400, resp.text
        detail = resp.json()["detail"]
        assert detail["code"] == "provider_config_rejected"
        assert {"code": "cannot_clear_stored_secret", "field": "secret_key"} in detail["errors"]

    def test_the_stored_secret_survives_the_refusal(self, client, db):
        """The point of the guard: the encrypted value is the only copy."""
        user = _create_user(db, suffix="pp-clr2")
        cookies = _auth_cookie(user)
        provider_id = self._create_stripe(client, cookies)

        client.put(
            f"/api/v1/payment-providers/{provider_id}",
            json={"config": {**VALID_CONFIGS["stripe"], "secret_key": ""}},
            cookies=cookies,
        )

        provider = db.query(PaymentProvider).filter(
            PaymentProvider.id == provider_id
        ).first()
        db.refresh(provider)
        decrypted = decrypt_config(provider.config, get_sensitive_fields("stripe"))
        assert decrypted["secret_key"] == VALID_CONFIGS["stripe"]["secret_key"]

    def test_every_blanked_secret_is_named_at_once(self, client, db):
        """Three fields emptied by one paste-gone-wrong report as three."""
        user = _create_user(db, suffix="pp-clr3")
        cookies = _auth_cookie(user)
        provider_id = self._create_stripe(client, cookies)

        resp = client.put(
            f"/api/v1/payment-providers/{provider_id}",
            json={"config": {"secret_key": "", "publishable_key": "", "webhook_secret": ""}},
            cookies=cookies,
        )

        assert resp.status_code == 400
        fields = {e["field"] for e in resp.json()["detail"]["errors"]}
        # `publishable_key` is not sensitive — it is readable on the screen and
        # recoverable, so emptying it stays a normal edit.
        assert fields == {"secret_key", "webhook_secret"}

    def test_blanking_a_secret_on_a_live_provider_is_refused(self, client, db):
        user = _create_user(db, suffix="pp-clr4")
        cookies = _auth_cookie(user)
        provider_id = self._create_stripe(client, cookies, status="active")

        resp = client.put(
            f"/api/v1/payment-providers/{provider_id}",
            json={"config": {**VALID_CONFIGS["stripe"], "webhook_secret": ""}},
            cookies=cookies,
        )

        assert resp.status_code == 400, resp.text
        provider = db.query(PaymentProvider).filter(
            PaymentProvider.id == provider_id
        ).first()
        db.refresh(provider)
        decrypted = decrypt_config(provider.config, get_sensitive_fields("stripe"))
        assert decrypted["webhook_secret"] == VALID_CONFIGS["stripe"]["webhook_secret"]

    def test_a_field_with_nothing_stored_may_still_be_left_empty(self, client, db):
        """The half-filled config stays savable: this guards a *stored* value,
        not the act of saving a blank."""
        user = _create_user(db, suffix="pp-clr5")
        cookies = _auth_cookie(user)
        create_resp = client.post(
            "/api/v1/payment-providers/",
            json={
                "provider_type": "stripe",
                "display_name": "Stripe",
                "status": "disabled",
                "config": {"secret_key": "sk_test_abc123"},
            },
            cookies=cookies,
        )
        assert create_resp.status_code == 201, create_resp.text
        provider_id = create_resp.json()["id"]

        resp = client.put(
            f"/api/v1/payment-providers/{provider_id}",
            json={"config": {"secret_key": "****c123", "webhook_secret": ""}},
            cookies=cookies,
        )

        assert resp.status_code == 200, resp.text

    def test_replacing_a_secret_outright_still_works(self, client, db):
        """The documented way to remove a secret is to paste another over it."""
        user = _create_user(db, suffix="pp-clr6")
        cookies = _auth_cookie(user)
        provider_id = self._create_stripe(client, cookies)

        resp = client.put(
            f"/api/v1/payment-providers/{provider_id}",
            json={"config": {**VALID_CONFIGS["stripe"], "secret_key": "sk_test_replaced"}},
            cookies=cookies,
        )

        assert resp.status_code == 200, resp.text
        provider = db.query(PaymentProvider).filter(
            PaymentProvider.id == provider_id
        ).first()
        db.refresh(provider)
        decrypted = decrypt_config(provider.config, get_sensitive_fields("stripe"))
        assert decrypted["secret_key"] == "sk_test_replaced"


class TestAnOutOfRangeOptionIsRefusedOnSave:
    """The other half of #406: option membership was checked only when a
    provider became member-facing, so a disabled row stored an environment no
    adapter knows and it surfaced at activation, or at a payment."""

    def test_a_disabled_provider_refuses_an_unknown_environment(self, client, db):
        user = _create_user(db, suffix="pp-opt1")

        resp = client.post(
            "/api/v1/payment-providers/",
            json={
                "provider_type": "redsys",
                "display_name": "Redsys",
                "status": "disabled",
                "config": {**VALID_CONFIGS["redsys"], "environment": "staging"},
            },
            cookies=_auth_cookie(user),
        )

        assert resp.status_code == 400, resp.text
        assert {
            "code": "invalid_option",
            "field": "environment",
            "options": ["test", "production"],
        } in resp.json()["detail"]["errors"]

    def test_the_refused_option_is_not_stored(self, client, db):
        user = _create_user(db, suffix="pp-opt2")
        provider = _create_provider(db, provider_type="redsys", status="disabled")

        client.put(
            f"/api/v1/payment-providers/{provider.id}",
            json={"config": {**VALID_CONFIGS["redsys"], "environment": "staging"}},
            cookies=_auth_cookie(user),
        )

        db.refresh(provider)
        assert provider.config["environment"] == "test"

    def test_a_known_environment_still_saves(self, client, db):
        user = _create_user(db, suffix="pp-opt3")
        provider = _create_provider(db, provider_type="redsys", status="disabled")

        resp = client.put(
            f"/api/v1/payment-providers/{provider.id}",
            json={"config": {**VALID_CONFIGS["redsys"], "environment": "production"}},
            cookies=_auth_cookie(user),
        )

        assert resp.status_code == 200, resp.text


# --- Test Connection ---


class TestTestProvider:
    def test_valid_stripe_config(self, client, db):
        from unittest.mock import patch, MagicMock

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
                    "webhook_secret": "whsec_test789",
                },
            },
            cookies=cookies,
        )
        provider_id = create_resp.json()["id"]

        with patch("app.domains.billing.providers.stripe_provider.stripe.Account.retrieve") as mock_retrieve:
            mock_account = MagicMock()
            mock_account.id = "acct_test123"
            mock_account.country = "ES"
            mock_account.settings.dashboard.display_name = "Test Club"
            mock_retrieve.return_value = mock_account

            resp = client.post(
                f"/api/v1/payment-providers/{provider_id}/test", cookies=cookies
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_invalid_stripe_config(self, client, db):
        from unittest.mock import patch
        import stripe

        user = _create_user(db, suffix="pp-test2")
        cookies = _auth_cookie(user)
        create_resp = client.post(
            "/api/v1/payment-providers/",
            json={
                "provider_type": "stripe",
                "display_name": "Stripe",
                "config": {
                    "secret_key": "sk_test_invalid",
                    "publishable_key": "pk_test_xyz",
                    "webhook_secret": "whsec_test",
                },
            },
            cookies=cookies,
        )
        provider_id = create_resp.json()["id"]

        with patch("app.domains.billing.providers.stripe_provider.stripe.Account.retrieve") as mock_retrieve:
            mock_retrieve.side_effect = stripe.AuthenticationError(
                "Invalid API Key provided"
            )

            resp = client.post(
                f"/api/v1/payment-providers/{provider_id}/test", cookies=cookies
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["errors"] == [{"code": "authentication_failed"}]
        # Stripe's own words are passed through rather than translated.
        assert data["message"] == "Invalid API Key provided"

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


class TestAdapterlessTypesCannotGoLive:
    """A config schema is not an adapter.

    `goCardless` and `paypal` have a schema and no implementation, so before
    #340 one could be created, validated, tested and switched to `active` —
    leaving an administrator told a method was live that no member is ever
    offered, because the member-facing pages gate on `stripe`/`redsys` by name.
    """

    def test_creating_an_adapterless_provider_is_refused(self, client, db):
        user = _create_user(db, suffix="pp-unavail1")
        payload = {
            "provider_type": "goCardless",
            "display_name": "GoCardless",
            "status": "disabled",
            "config": {
                "access_token": "token",
                "webhook_secret": "secret",
                "environment": "sandbox",
            },
        }
        resp = client.post(
            "/api/v1/payment-providers/", json=payload, cookies=_auth_cookie(user)
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "provider_type_unavailable"
        assert resp.json()["detail"]["provider_type"] == "goCardless"

    def test_paypal_is_refused_too(self, client, db):
        user = _create_user(db, suffix="pp-unavail2")
        payload = {
            "provider_type": "paypal",
            "display_name": "PayPal",
            "status": "disabled",
            "config": {
                "client_id": "id",
                "client_secret": "secret",
                "environment": "sandbox",
            },
        }
        resp = client.post(
            "/api/v1/payment-providers/", json=payload, cookies=_auth_cookie(user)
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "provider_type_unavailable"

    def test_an_existing_adapterless_row_cannot_be_activated(self, client, db):
        """Instances seeded before #340 already hold these rows."""
        user = _create_user(db, suffix="pp-unavail3")
        provider = _create_provider(
            db, provider_type="goCardless", status="disabled"
        )
        resp = client.post(
            f"/api/v1/payment-providers/{provider.id}/toggle",
            cookies=_auth_cookie(user),
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "provider_type_unavailable"

    def test_an_available_type_still_activates(self, client, db):
        """The guard must not catch the three types that do work."""
        user = _create_user(db, suffix="pp-unavail4")
        provider = _create_provider(db, provider_type="stripe", status="disabled")
        resp = client.post(
            f"/api/v1/payment-providers/{provider.id}/toggle",
            cookies=_auth_cookie(user),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"


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

    def test_stripe_is_available(self, client, db):
        user = _create_user(db, suffix="pp-types3")
        cookies = _auth_cookie(user)
        resp = client.get("/api/v1/payment-providers/types", cookies=cookies)
        data = resp.json()
        stripe = next(t for t in data if t["provider_type"] == "stripe")
        assert stripe["available"] is True

    def test_types_include_fields(self, client, db):
        user = _create_user(db, suffix="pp-types4")
        cookies = _auth_cookie(user)
        resp = client.get("/api/v1/payment-providers/types", cookies=cookies)
        data = resp.json()
        stripe = next(t for t in data if t["provider_type"] == "stripe")
        assert len(stripe["fields"]) == 3
        assert stripe["sensitive_fields"] == ["secret_key", "webhook_secret"]


class TestTestResponseIsTranslatable:
    """`/test` used to hand the UI a rendered English sentence (#223)."""

    def test_a_local_validation_failure_returns_codes_not_prose(self, client, db):
        user = _create_user(db, suffix="pp-i18n1")
        provider = _create_provider(db, provider_type="sepa_direct_debit", config={"format": "wrong"})
        cookies = _auth_cookie(user)

        resp = client.post(
            f"/api/v1/payment-providers/{provider.id}/test", cookies=cookies
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["message"] is None
        assert data["errors"] == [
            {"code": "invalid_option", "field": "format", "options": ["pain.008.001.02"]}
        ]

    def test_a_valid_config_reports_success_with_nothing_to_render(self, client, db):
        user = _create_user(db, suffix="pp-i18n2")
        provider = _create_provider(db, provider_type="sepa_direct_debit")
        cookies = _auth_cookie(user)

        resp = client.post(
            f"/api/v1/payment-providers/{provider.id}/test", cookies=cookies
        )

        data = resp.json()
        assert data["success"] is True
        assert data["errors"] == []

    def test_redsys_reports_its_stricter_rule_as_a_code(self, client, db):
        """Redsys checks a merchant-code length activation does not, and that
        rule has to be translatable too."""
        user = _create_user(db, suffix="pp-i18n3")
        provider = _create_provider(
            db,
            provider_type="redsys",
            config={**VALID_CONFIGS["redsys"], "merchant_code": "123"},
        )
        cookies = _auth_cookie(user)

        resp = client.post(
            f"/api/v1/payment-providers/{provider.id}/test", cookies=cookies
        )

        data = resp.json()
        assert data["success"] is False
        assert {
            "code": "must_be_digits_between",
            "field": "merchant_code",
            "min": 7,
            "max": 9,
        } in data["errors"]
