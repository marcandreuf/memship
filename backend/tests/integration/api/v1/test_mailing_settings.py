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
    build_field_node,
    resolve_mailing_config,
)
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person

# Resend has no account to send as, so a key alone is not a usable provider.
SENDER = build_field_node("noreply@club.example", False)

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
    person = Person(first_name="T", last_name="U", email=f"{suffix}-{role}@examplee6e3b1.com")
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

    def test_env_only_active_falls_to_smtp(self, db, monkeypatch):
        from app.core.config import settings

        _clear_env(monkeypatch)
        monkeypatch.setattr(settings, "SMTP_HOST", "smtp.other.com", raising=False)
        _org(db)

        resolved = resolve_mailing_config(db)
        assert resolved.active == "smtp"
        # An env-only install keeps dialling its own server (#442).
        assert resolved.smtp_endpoint() == ("smtp.other.com", 587, True)

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
        assert resolve_mailing_config(db).active is None

        org.mailing_config = {
            "active_provider": "resend",
            "resend": {"api_key": {"value": "k", "secret": False}, "from_email": SENDER},
        }
        db.flush()
        assert resolve_mailing_config(db).active == "resend"

    def test_resend_needs_a_sender(self, db, monkeypatch):
        """#439: a Resend key with no From address is refused on every send."""
        _clear_env(monkeypatch)
        org = _org(db)
        org.mailing_config = {"resend": {"api_key": {"value": "k", "secret": False}}}
        db.flush()

        resend = resolve_mailing_config(db).resend
        assert resend.ready is False
        assert resend.sources["from_email"] == "none"

    def test_resend_sender_falls_back_to_smtp_from(self, db, monkeypatch):
        from app.core.config import settings

        _clear_env(monkeypatch)
        monkeypatch.setattr(settings, "SMTP_FROM", "noreply@club.example", raising=False)
        org = _org(db)
        org.mailing_config = {"resend": {"api_key": {"value": "k", "secret": False}}}
        db.flush()

        resend = resolve_mailing_config(db).resend
        assert resend.get("from_email") == "noreply@club.example"
        assert resend.sources["from_email"] == "env"
        assert resend.ready is True

        monkeypatch.setattr(settings, "RESEND_FROM_EMAIL", "club@resend.example", raising=False)
        assert resolve_mailing_config(db).resend.get("from_email") == "club@resend.example"

    def test_stored_smtp_endpoint_wins_over_env(self, db, monkeypatch):
        from app.core.config import settings

        _clear_env(monkeypatch)
        monkeypatch.setattr(settings, "SMTP_HOST", "smtp.other.com", raising=False)
        org = _org(db)
        org.mailing_config = {
            "active_provider": "smtp",
            "smtp": {
                "host": {"value": "mail.club.example", "secret": False},
                "port": {"value": "2525", "secret": False},
                "tls": {"value": "false", "secret": False},
                "user": {"value": "secretaria@club.example", "secret": False},
                "password": {"value": "pw", "secret": False},
            },
        }
        db.flush()

        resolved = resolve_mailing_config(db)
        assert resolved.active == "smtp"
        assert resolved.smtp_endpoint() == ("mail.club.example", 2525, False)

    def test_unset_port_and_tls_read_as_defaults_not_env(self, db, monkeypatch):
        """The typed settings always hold a value; only a configured one is "env"."""
        _clear_env(monkeypatch)
        _org(db)

        sources = resolve_mailing_config(db).flat_sources()
        assert sources["smtp.port"] == "default"
        assert sources["smtp.tls"] == "default"
        assert sources["smtp.host"] == "none"

    def test_smtp_needs_a_host_and_a_sender(self, db, monkeypatch):
        _clear_env(monkeypatch)
        org = _org(db)
        org.mailing_config = {"smtp": {"user": {"value": "a@club.example", "secret": False}}}
        db.flush()
        assert resolve_mailing_config(db).smtp.ready is False

        org.mailing_config = {"smtp": {"host": {"value": "mail.club.example", "secret": False}}}
        db.flush()
        assert resolve_mailing_config(db).smtp.ready is False  # no sender address

        org.mailing_config = {
            "smtp": {
                "host": {"value": "mail.club.example", "secret": False},
                "from_email": {"value": "socios@club.example", "secret": False},
            }
        }
        db.flush()
        # No user or password: a relay that trusts the server needs neither.
        assert resolve_mailing_config(db).smtp.ready is True

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

    def _verify(self, client, provider):
        resp = client.post("/api/v1/settings/mailing/test", json={"provider": provider})
        assert resp.json()["ok"] is True

    def test_activate_tested_provider(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        _org(db)
        self._admin(client, db, "put-act")

        client.put("/api/v1/settings/mailing", json={"resend": {"api_key": {"value": "re_key"}, "from_email": "noreply@club.example"}})
        self._verify(client, "resend")
        resp = client.put("/api/v1/settings/mailing", json={"active_provider": "resend"})
        assert resp.status_code == 200
        assert resp.json()["active_provider"] == "resend"

    def test_cannot_activate_untested_provider(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        org = _org(db)
        org.mailing_config = {"resend": {"api_key": build_field_node("re_key", True), "from_email": SENDER}}
        db.flush()
        self._admin(client, db, "put-untested")

        resp = client.put("/api/v1/settings/mailing", json={"active_provider": "resend"})
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "mailing_provider_not_verified"
        assert "active_provider" not in org.mailing_config

    def test_cannot_activate_failing_provider(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        org = _org(db)
        org.mailing_config = {"resend": {"api_key": build_field_node("re_key", True), "from_email": SENDER}}
        db.flush()
        self._admin(client, db, "put-failing")

        def refuse(*args, **kwargs):
            raise ConnectionRefusedError("down")

        monkeypatch.setattr(email_module, "_dispatch", refuse)
        client.post("/api/v1/settings/mailing/test", json={"provider": "resend"})

        resp = client.put("/api/v1/settings/mailing", json={"active_provider": "resend"})
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "mailing_provider_not_verified"

    def test_credentials_changed_with_activation_need_their_own_test(self, client, db, monkeypatch):
        """The old key's passing test proves nothing about the one replacing it."""
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        org = _org(db)
        org.mailing_config = {"resend": {"api_key": build_field_node("re_old", True), "from_email": SENDER}}
        db.flush()
        self._admin(client, db, "put-swap")
        self._verify(client, "resend")

        resp = client.put(
            "/api/v1/settings/mailing",
            json={"resend": {"api_key": {"value": "re_new"}}, "active_provider": "resend"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "mailing_provider_not_verified"
        # The whole request is refused, credentials included.
        assert secrets_crypto.decrypt(org.mailing_config["resend"]["api_key"]["value"]) == "re_old"

    def test_keeping_the_active_provider_is_not_gated(self, client, db, monkeypatch):
        """An install activated before the gate keeps working when its settings are saved."""
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        org = _org(db)
        org.mailing_config = {
            "active_provider": "resend",
            "resend": {"api_key": build_field_node("re_key", True)},
        }
        db.flush()
        self._admin(client, db, "put-keep")

        resp = client.put(
            "/api/v1/settings/mailing",
            json={"active_provider": "resend", "resend": {"from_email": "club@example.org"}},
        )
        assert resp.status_code == 200
        assert resp.json()["active_provider"] == "resend"

    def test_deactivating_is_never_gated(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        org = _org(db)
        org.mailing_config = {
            "active_provider": "resend",
            "resend": {"api_key": build_field_node("re_key", True)},
        }
        db.flush()
        self._admin(client, db, "put-off")

        resp = client.put("/api/v1/settings/mailing", json={"active_provider": None})
        assert resp.status_code == 200
        assert resp.json()["active_provider"] is None

    def test_cannot_activate_unready_provider(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        org = _org(db)
        self._admin(client, db, "put-unready")

        resp = client.put(
            "/api/v1/settings/mailing",
            json={"active_provider": "smtp"},  # no smtp host
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
            "smtp": {
                "host": {"value": "smtp.gmail.com", "secret": False},
                "user": {"value": "club@gmail.com", "secret": False},
                "password": build_field_node("app-pw", True),
            },
        }
        db.flush()
        self._admin(client, db, "put-switch")
        self._verify(client, "smtp")

        resp = client.put("/api/v1/settings/mailing", json={"active_provider": "smtp"})
        assert resp.status_code == 200
        assert resp.json()["active_provider"] == "smtp"
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
            json={"resend": {"api_key": {"value": "re_supersecret"}, "from_email": "noreply@club.example"}},
        )
        self._verify(client, "resend")
        client.put("/api/v1/settings/mailing", json={"active_provider": "resend"})
        entries = (
            db.query(AuditLog)
            .filter(AuditLog.table_name == "organization_settings", AuditLog.action == "update")
            .all()
        )
        assert len(entries) >= 2
        saved, activated = entries[-2], entries[-1]
        assert "mailing_config.resend.api_key" in saved.changed_fields
        assert "mailing_config.active_provider" in activated.changed_fields
        assert "re_supersecret" not in str([e.changed_fields for e in entries])


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
        resp = client.post("/api/v1/settings/mailing/test", json={"provider": "smtp"})
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "mailing_provider_not_ready"

    def test_sends_via_requested_provider_even_when_not_active(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        org = _org(db)
        # Resend has creds but is NOT the active provider.
        org.mailing_config = {"resend": {"api_key": build_field_node("re_key", True), "from_email": SENDER}}
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
        assert calls["to"] == "test-send-super_admin@examplee6e3b1.com"  # defaults to caller email

    def test_reports_transport_failure(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        org = _org(db)
        org.mailing_config = {"resend": {"api_key": build_field_node("re_key", True), "from_email": SENDER}}
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

class TestMailTransportHealth:
    """#338: the screen tells a working credential from an untried or failing one."""

    def _admin(self, client, db, suffix):
        admin = _create_user(db, "super_admin", suffix)
        client.cookies.update(_auth_cookie(admin))
        return admin

    def _resend_org(self, db, monkeypatch, key="re_key"):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        org = _org(db)
        org.mailing_config = {"resend": {"api_key": build_field_node(key, True), "from_email": SENDER}}
        db.flush()
        return org

    def _health(self, client, provider="resend"):
        return client.get("/api/v1/settings/mailing").json()[provider]["health"]

    def test_untried_credentials_are_unverified(self, client, db, monkeypatch):
        self._resend_org(db, monkeypatch)
        self._admin(client, db, "health-new")

        body = client.get("/api/v1/settings/mailing").json()
        assert body["resend"]["ready"] is True
        assert body["resend"]["health"] == {
            "status": "unverified",
            "last_success_at": None,
            "last_failure_at": None,
            "last_failure": None,
        }
        assert body["smtp"]["health"]["status"] == "unverified"

    def test_passing_test_send_marks_provider_ok(self, client, db, monkeypatch):
        self._resend_org(db, monkeypatch)
        self._admin(client, db, "health-ok")

        assert client.post("/api/v1/settings/mailing/test", json={"provider": "resend"}).json()["ok"]

        health = self._health(client)
        assert health["status"] == "ok"
        assert health["last_success_at"] is not None
        assert health["last_failure"] is None

    def test_failing_test_send_marks_provider_failing(self, client, db, monkeypatch):
        import smtplib

        self._resend_org(db, monkeypatch)
        self._admin(client, db, "health-fail")

        def refuse(*args, **kwargs):
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")

        monkeypatch.setattr(email_module, "_dispatch", refuse)
        client.post("/api/v1/settings/mailing/test", json={"provider": "resend"})

        health = self._health(client)
        assert health["status"] == "failing"
        assert health["last_failure"] == "invalid_credentials"
        assert health["last_success_at"] is None
        # The classified reason only — never the transport's own text.
        assert "bad credentials" not in client.get("/api/v1/settings/mailing").text

    def test_recovery_keeps_the_last_failure_on_record(self, client, db, monkeypatch):
        self._resend_org(db, monkeypatch)
        self._admin(client, db, "health-recover")

        def refuse(*args, **kwargs):
            raise ConnectionRefusedError("down")

        monkeypatch.setattr(email_module, "_dispatch", refuse)
        client.post("/api/v1/settings/mailing/test", json={"provider": "resend"})
        monkeypatch.setattr(email_module, "_dispatch", lambda *a, **k: True)
        client.post("/api/v1/settings/mailing/test", json={"provider": "resend"})

        health = self._health(client)
        assert health["status"] == "ok"
        assert health["last_failure"] == "transport_unavailable"

    def test_replaced_credential_is_unverified_again(self, client, db, monkeypatch):
        self._resend_org(db, monkeypatch)
        self._admin(client, db, "health-replace")
        client.post("/api/v1/settings/mailing/test", json={"provider": "resend"})
        assert self._health(client)["status"] == "ok"

        client.put(
            "/api/v1/settings/mailing",
            json={"resend": {"api_key": {"value": "re_other_key"}}},
        )

        assert self._health(client)["status"] == "unverified"

    def test_changed_env_credential_is_unverified_again(self, client, db, monkeypatch):
        """A key rotated in .env, not in the screen, must not inherit the old history."""
        from app.core.config import settings

        _clear_env(monkeypatch)
        _org(db)
        monkeypatch.setattr(settings, "RESEND_API_KEY", "env-key-1", raising=False)
        monkeypatch.setattr(settings, "RESEND_FROM_EMAIL", "noreply@club.example", raising=False)
        self._admin(client, db, "health-env")
        client.post("/api/v1/settings/mailing/test", json={"provider": "resend"})
        assert self._health(client)["status"] == "ok"

        monkeypatch.setattr(settings, "RESEND_API_KEY", "env-key-2", raising=False)

        assert self._health(client)["status"] == "unverified"

    def test_recording_leaves_an_env_only_install_env_only(self, db, monkeypatch):
        """Health must not land in mailing_config: any key there switches off env mail."""
        from app.core.config import settings
        from app.domains.mailing.mailing_health import record_outcome

        _clear_env(monkeypatch)
        monkeypatch.setattr(settings, "RESEND_API_KEY", "env-key", raising=False)
        org = _org(db)

        record_outcome(db, resolve_mailing_config(db), "resend", None)
        db.flush()

        assert org.mailing_config == {}
        assert resolve_mailing_config(db).active == "resend"


class TestSmtpProvider:
    """#442: any SMTP server is configurable from the screen, not only through .env."""

    def _admin(self, client, db, suffix):
        admin = _create_user(db, "super_admin", suffix)
        client.cookies.update(_auth_cookie(admin))
        return admin

    def test_stores_host_port_and_tls(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        org = _org(db)
        self._admin(client, db, "smtp-put")

        resp = client.put(
            "/api/v1/settings/mailing",
            json={
                "smtp": {
                    "host": "mail.club.example",
                    "port": 2525,
                    "tls": False,
                    "user": "secretaria@club.example",
                    "password": {"value": "s3cret"},
                }
            },
        )
        assert resp.status_code == 200
        smtp = resp.json()["smtp"]
        assert (smtp["host"], smtp["port"], smtp["tls"]) == ("mail.club.example", 2525, False)
        assert smtp["user"] == "secretaria@club.example"
        assert smtp["password"] == {"configured": True, "last4": "cret"}
        assert smtp["ready"] is True
        assert "s3cret" not in resp.text
        node = org.mailing_config["smtp"]
        assert node["port"] == {"value": "2525", "secret": False}
        assert node["tls"] == {"value": "false", "secret": False}
        assert secrets_crypto.decrypt(node["password"]["value"]) == "s3cret"

    def test_rejects_an_out_of_range_port(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _org(db)
        self._admin(client, db, "smtp-port")

        resp = client.put("/api/v1/settings/mailing", json={"smtp": {"port": 70000}})
        assert resp.status_code == 422

    def test_env_only_smtp_install_reports_smtp(self, client, db, monkeypatch):
        """No longer labelled Gmail while talking to some other host."""
        from app.core.config import settings

        _clear_env(monkeypatch)
        monkeypatch.setattr(settings, "SMTP_HOST", "smtp.other.com", raising=False)
        monkeypatch.setattr(settings, "SMTP_USER", "club@other.com", raising=False)
        _org(db)
        self._admin(client, db, "smtp-env")

        body = client.get("/api/v1/settings/mailing").json()
        assert body["active_provider"] == "smtp"
        assert body["smtp"]["host"] == "smtp.other.com"
        assert body["sources"]["smtp.host"] == "env"
