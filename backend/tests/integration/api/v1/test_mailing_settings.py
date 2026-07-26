"""Tests for the superadmin mailing-provider configuration screen (v1.3.2).

Covers the DB-wins-env-fallback resolver, the one-of-N ``active_provider`` rule,
the masked GET / write-only PUT endpoints, and the verify-before-activate
test-send endpoint. Reuses the v1.3.1 encryption helper unchanged.
"""

import pytest
from cryptography.fernet import Fernet

from app.core import email as email_module
from app.core.security import secrets_crypto
from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.audit.models import AuditLog
from app.domains.auth.models import User
from app.domains.mailing.mailing_config import (
    GMAIL_SMTP_HOST,
    build_field_node,
    resolve_mailing_config,
)
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person

MAIL_ENV_VARS = (
    "RESEND_API_KEY",
    "RESEND_FROM_EMAIL",
    "SMTP_HOST",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "SMTP_FROM",
)


def _set_key(monkeypatch, key: str | None = None):
    from app.core.config import settings

    monkeypatch.setattr(
        settings, "MEMSHIP_SECRET_KEY", key or Fernet.generate_key().decode(), raising=False
    )


@pytest.fixture(autouse=True)
def _reset_secret_key_cache():
    secrets_crypto.reset_key_cache()
    yield
    secrets_crypto.reset_key_cache()


def _clear_env(monkeypatch):
    """Blank every mail env var so env fallback does not mask DB assertions."""
    from app.core.config import settings

    for name in MAIL_ENV_VARS:
        monkeypatch.setattr(settings, name, "", raising=False)


def _org(db):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(id=1, name="Test Club")
        db.add(org)
        db.flush()
    org.mailing_config = {}
    db.flush()
    return org


def _create_user(db, role="super_admin", suffix="mail"):
    person = Person(first_name="T", last_name="U", email=f"{suffix}-{role}@test.com")
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


class TestResolver:
    def test_db_value_wins_over_env(self, db, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "RESEND_API_KEY", "env-key", raising=False)
        org = _org(db)
        org.mailing_config = {"resend": {"api_key": {"value": "db-key", "secret": False}}}
        db.flush()

        resend = resolve_mailing_config(db).resend
        assert resend.get("api_key") == "db-key"
        assert resend.sources["api_key"] == "db"

    def test_env_fallback_when_db_empty(self, db, monkeypatch):
        from app.core.config import settings

        _clear_env(monkeypatch)
        monkeypatch.setattr(settings, "RESEND_API_KEY", "env-key", raising=False)
        _org(db)

        resend = resolve_mailing_config(db).resend
        assert resend.get("api_key") == "env-key"
        assert resend.sources["api_key"] == "env"

    def test_env_only_active_is_resend_first(self, db, monkeypatch):
        """No DB node → legacy behaviour: Resend wins when both env transports set."""
        from app.core.config import settings

        _clear_env(monkeypatch)
        monkeypatch.setattr(settings, "RESEND_API_KEY", "env-key", raising=False)
        monkeypatch.setattr(settings, "SMTP_HOST", "smtp.other.com", raising=False)
        _org(db)

        assert resolve_mailing_config(db).active == "resend"

    def test_env_only_active_falls_to_gmail(self, db, monkeypatch):
        from app.core.config import settings

        _clear_env(monkeypatch)
        monkeypatch.setattr(settings, "SMTP_HOST", "smtp.other.com", raising=False)
        _org(db)

        resolved = resolve_mailing_config(db)
        assert resolved.active == "gmail"
        # A legacy SMTP host is honoured, not overridden by the Gmail constant.
        assert resolved.gmail_smtp()[0] == "smtp.other.com"

    def test_db_node_without_active_is_inactive(self, db, monkeypatch):
        """Saving credentials must not auto-activate a provider."""
        _clear_env(monkeypatch)
        org = _org(db)
        org.mailing_config = {"resend": {"api_key": {"value": "k", "secret": False}}}
        db.flush()

        assert resolve_mailing_config(db).active is None

    def test_explicit_active_gated_on_ready(self, db, monkeypatch):
        _clear_env(monkeypatch)
        org = _org(db)
        # active points at resend but no api_key resolves → not active.
        org.mailing_config = {"active_provider": "resend", "resend": {}}
        db.flush()
        assert resolve_mailing_config(db).active is None

        org.mailing_config = {
            "active_provider": "resend",
            "resend": {"api_key": {"value": "k", "secret": False}},
        }
        db.flush()
        assert resolve_mailing_config(db).active == "resend"

    def test_ui_gmail_pins_google_smtp_host(self, db, monkeypatch):
        _clear_env(monkeypatch)
        org = _org(db)
        org.mailing_config = {
            "active_provider": "gmail",
            "gmail": {
                "user": {"value": "club@gmail.com", "secret": False},
                "app_password": {"value": "app-pw", "secret": False},
            },
        }
        db.flush()

        resolved = resolve_mailing_config(db)
        assert resolved.active == "gmail"
        assert resolved.gmail_smtp() == (GMAIL_SMTP_HOST, 587, True)

    def test_secret_decrypts(self, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        org = _org(db)
        org.mailing_config = {"resend": {"api_key": build_field_node("re_secret", True)}}
        db.flush()

        assert resolve_mailing_config(db).resend.get("api_key") == "re_secret"


class TestGetMailingEndpoint:
    def test_requires_super_admin(self, client, db):
        _org(db)
        member = _create_user(db, "member", "get-mbr")
        client.cookies.update(_auth_cookie(member))
        assert client.get("/api/v1/settings/mailing").status_code == 403

    def test_never_returns_secret_values(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        org = _org(db)
        org.mailing_config = {
            "active_provider": "resend",
            "resend": {
                "from_email": {"value": "noreply@club.example", "secret": False},
                "api_key": build_field_node("re_very_secret_1234", True),
            },
        }
        db.flush()
        admin = _create_user(db, "super_admin", "get-sa")
        client.cookies.update(_auth_cookie(admin))

        resp = client.get("/api/v1/settings/mailing")
        body = resp.json()
        assert body["active_provider"] == "resend"
        assert body["resend"]["from_email"] == "noreply@club.example"
        assert body["resend"]["api_key"]["configured"] is True
        assert body["resend"]["api_key"]["last4"] == "1234"
        assert body["resend"]["ready"] is True
        assert "re_very_secret_1234" not in resp.text


class TestPutMailingEndpoint:
    def _admin(self, client, db, suffix):
        admin = _create_user(db, "super_admin", suffix)
        client.cookies.update(_auth_cookie(admin))
        return admin

    def test_non_super_admin_forbidden(self, client, db):
        _org(db)
        member = _create_user(db, "member", "put-mbr")
        client.cookies.update(_auth_cookie(member))
        resp = client.put("/api/v1/settings/mailing", json={"resend": {"from_email": "x@y.com"}})
        assert resp.status_code == 403

    def test_encrypts_secret_before_persisting(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        org = _org(db)
        self._admin(client, db, "put-enc")

        resp = client.put(
            "/api/v1/settings/mailing",
            json={"resend": {"api_key": {"value": "re_topsecret"}}},
        )
        assert resp.status_code == 200
        stored = org.mailing_config["resend"]["api_key"]
        assert stored["secret"] is True
        assert stored["value"] != "re_topsecret"
        assert secrets_crypto.decrypt(stored["value"]) == "re_topsecret"

    def test_blank_secret_leaves_prior_value(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        org = _org(db)
        org.mailing_config = {"resend": {"api_key": build_field_node("orig", True)}}
        db.flush()
        self._admin(client, db, "put-blank")

        resp = client.put(
            "/api/v1/settings/mailing",
            json={"resend": {"from_email": "new@club.example"}},
        )
        assert resp.status_code == 200
        assert secrets_crypto.decrypt(org.mailing_config["resend"]["api_key"]["value"]) == "orig"

    def test_clear_wipes_secret(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        org = _org(db)
        org.mailing_config = {"resend": {"api_key": build_field_node("orig", True)}}
        db.flush()
        self._admin(client, db, "put-clear")

        resp = client.put(
            "/api/v1/settings/mailing",
            json={"resend": {"api_key": {"clear": True}}},
        )
        assert resp.status_code == 200
        assert "api_key" not in org.mailing_config["resend"]

    def test_activate_ready_provider(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        _org(db)
        self._admin(client, db, "put-act")

        resp = client.put(
            "/api/v1/settings/mailing",
            json={
                "resend": {"api_key": {"value": "re_key"}},
                "active_provider": "resend",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["active_provider"] == "resend"

    def test_cannot_activate_unready_provider(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        org = _org(db)
        self._admin(client, db, "put-unready")

        resp = client.put(
            "/api/v1/settings/mailing",
            json={"active_provider": "gmail"},  # no gmail creds
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "mailing_provider_not_ready"
        # Nothing persisted.
        assert (org.mailing_config or {}).get("active_provider") is None

    def test_switching_active_leaves_other_creds_intact(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        org = _org(db)
        org.mailing_config = {
            "active_provider": "resend",
            "resend": {"api_key": build_field_node("re_key", True)},
            "gmail": {
                "user": {"value": "club@gmail.com", "secret": False},
                "app_password": build_field_node("app-pw", True),
            },
        }
        db.flush()
        self._admin(client, db, "put-switch")

        resp = client.put("/api/v1/settings/mailing", json={"active_provider": "gmail"})
        assert resp.status_code == 200
        assert resp.json()["active_provider"] == "gmail"
        # Resend creds untouched.
        assert secrets_crypto.decrypt(org.mailing_config["resend"]["api_key"]["value"]) == "re_key"

    def test_rejects_secret_write_without_key(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        monkeypatch.setattr(secrets_crypto, "_load_or_create_file_key", lambda: None)
        from app.core.config import settings

        monkeypatch.setattr(settings, "MEMSHIP_SECRET_KEY", "", raising=False)
        secrets_crypto.reset_key_cache()
        _org(db)
        self._admin(client, db, "put-nokey")

        resp = client.put(
            "/api/v1/settings/mailing",
            json={"resend": {"api_key": {"value": "re_key"}}},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "mailing_encryption_key_missing"

    def test_audit_written_without_values(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        _org(db)
        self._admin(client, db, "put-audit")

        client.put(
            "/api/v1/settings/mailing",
            json={"resend": {"api_key": {"value": "re_supersecret"}}, "active_provider": "resend"},
        )
        entries = (
            db.query(AuditLog)
            .filter(AuditLog.table_name == "organization_settings", AuditLog.action == "update")
            .all()
        )
        assert entries
        latest = entries[-1]
        assert "mailing_config.resend.api_key" in latest.changed_fields
        assert "mailing_config.active_provider" in latest.changed_fields
        assert "re_supersecret" not in str(latest.changed_fields)


class TestMailingTestEndpoint:
    def _admin(self, client, db, suffix):
        admin = _create_user(db, "super_admin", suffix)
        client.cookies.update(_auth_cookie(admin))
        return admin

    def test_requires_super_admin(self, client, db):
        _org(db)
        member = _create_user(db, "member", "test-mbr")
        client.cookies.update(_auth_cookie(member))
        resp = client.post("/api/v1/settings/mailing/test", json={"provider": "resend"})
        assert resp.status_code == 403

    def test_provider_not_ready(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _org(db)
        self._admin(client, db, "test-unready")
        resp = client.post("/api/v1/settings/mailing/test", json={"provider": "gmail"})
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "mailing_provider_not_ready"

    def test_sends_via_requested_provider_even_when_not_active(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        org = _org(db)
        # Resend has creds but is NOT the active provider.
        org.mailing_config = {"resend": {"api_key": build_field_node("re_key", True)}}
        db.flush()
        self._admin(client, db, "test-send")

        calls = {}

        def fake_dispatch(provider, resolved, to, subject, html_body, **kwargs):
            calls["provider"] = provider
            calls["to"] = to
            return True

        monkeypatch.setattr(email_module, "_dispatch", fake_dispatch)

        resp = client.post("/api/v1/settings/mailing/test", json={"provider": "resend"})
        assert resp.status_code == 200
        assert resp.json() == {"ok": True, "error": None}
        assert calls["provider"] == "resend"
        assert calls["to"] == "test-send-super_admin@test.com"  # defaults to caller email

    def test_reports_transport_failure(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        org = _org(db)
        org.mailing_config = {"resend": {"api_key": build_field_node("re_key", True)}}
        db.flush()
        self._admin(client, db, "test-fail")

        def boom(*args, **kwargs):
            raise RuntimeError("smtp auth failed")

        monkeypatch.setattr(email_module, "_dispatch", boom)

        resp = client.post("/api/v1/settings/mailing/test", json={"provider": "resend"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert "smtp auth failed" in body["error"]