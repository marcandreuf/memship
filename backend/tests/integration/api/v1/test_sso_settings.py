"""Tests for the superadmin SSO configuration screen (v1.3.1).

Covers the encryption helper, the DB-wins-env-fallback resolver, and the
masked GET / write-only PUT endpoints.
"""

import pytest
from cryptography.fernet import Fernet

from app.core.security import secrets_crypto
from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.audit.models import AuditLog
from app.domains.auth.models import User
from app.domains.auth.sso_config import (
    _resolve_provider,
    build_field_node,
    resolve_sso_config,
)
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


def _set_key(monkeypatch, key: str | None = None):
    from app.core.config import settings

    monkeypatch.setattr(
        settings, "MEMSHIP_SECRET_KEY", key or Fernet.generate_key().decode(), raising=False
    )


def _clear_key(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "MEMSHIP_SECRET_KEY", "", raising=False)


def _force_no_key(monkeypatch):
    """Simulate the only real 'no key' case: env unset and the key file unwritable."""
    _clear_key(monkeypatch)
    secrets_crypto.reset_key_cache()
    monkeypatch.setattr(secrets_crypto, "_load_or_create_file_key", lambda: None)


@pytest.fixture(autouse=True)
def _reset_secret_key_cache():
    secrets_crypto.reset_key_cache()
    yield
    secrets_crypto.reset_key_cache()


def _clear_env(monkeypatch):
    """Blank every SSO env var so env fallback does not mask DB assertions."""
    from app.core.config import settings

    for name in (
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "APPLE_CLIENT_ID",
        "APPLE_TEAM_ID",
        "APPLE_KEY_ID",
        "APPLE_PRIVATE_KEY",
    ):
        monkeypatch.setattr(settings, name, "", raising=False)


def _org(db):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(id=1, name="Test Club")
        db.add(org)
        db.flush()
    return org


def _create_user(db, role="super_admin", suffix="sso"):
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


class TestSecretsCrypto:
    def test_round_trip(self, monkeypatch):
        _set_key(monkeypatch)
        cipher = secrets_crypto.encrypt("super-secret")
        assert cipher != "super-secret"
        assert secrets_crypto.decrypt(cipher) == "super-secret"

    def test_decrypt_with_wrong_key_raises(self, monkeypatch):
        _set_key(monkeypatch)
        cipher = secrets_crypto.encrypt("x")
        _set_key(monkeypatch)  # rotate to a different key
        with pytest.raises(secrets_crypto.SecretDecryptError):
            secrets_crypto.decrypt(cipher)

    def test_unavailable_only_when_file_unwritable(self, monkeypatch):
        # Env unset + key file unwritable is the sole no-key case.
        _force_no_key(monkeypatch)
        assert secrets_crypto.secrets_available() is False
        with pytest.raises(secrets_crypto.SecretsKeyMissingError):
            secrets_crypto.encrypt("x")

    def test_available_with_key(self, monkeypatch):
        _set_key(monkeypatch)
        assert secrets_crypto.secrets_available() is True

    def test_auto_generates_file_key_when_no_env(self, monkeypatch, tmp_path):
        from app.core.config import settings

        _clear_key(monkeypatch)
        key_file = tmp_path / "secret.key"
        monkeypatch.setattr(settings, "SECRETS_KEY_FILE", str(key_file), raising=False)
        secrets_crypto.reset_key_cache()

        assert secrets_crypto.secrets_available() is True
        assert key_file.exists()
        cipher = secrets_crypto.encrypt("v")
        assert secrets_crypto.decrypt(cipher) == "v"

        # The generated key is stable across resolves — it is not regenerated.
        first = key_file.read_text(encoding="utf-8").strip()
        secrets_crypto.reset_key_cache()
        assert secrets_crypto.secrets_available() is True
        assert key_file.read_text(encoding="utf-8").strip() == first

    def test_env_key_wins_over_file(self, monkeypatch, tmp_path):
        from app.core.config import settings

        key_file = tmp_path / "secret.key"
        key_file.write_text(Fernet.generate_key().decode(), encoding="utf-8")
        monkeypatch.setattr(settings, "SECRETS_KEY_FILE", str(key_file), raising=False)
        secrets_crypto.reset_key_cache()
        env_key = Fernet.generate_key().decode()
        monkeypatch.setattr(settings, "MEMSHIP_SECRET_KEY", env_key, raising=False)

        assert secrets_crypto._resolve_key() == env_key


class TestResolver:
    def test_db_value_wins_over_env(self, db, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "env-id", raising=False)
        org = _org(db)
        org.sso_config = {"google": {"client_id": {"value": "db-id", "secret": False}}}
        db.flush()

        google = resolve_sso_config(db).google
        assert google.get("client_id") == "db-id"
        assert google.sources["client_id"] == "db"

    def test_env_fallback_when_db_empty(self, db, monkeypatch):
        from app.core.config import settings

        _clear_env(monkeypatch)
        monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "env-id", raising=False)
        _org(db).sso_config = {}
        db.flush()

        google = resolve_sso_config(db).google
        assert google.get("client_id") == "env-id"
        assert google.sources["client_id"] == "env"

    def test_env_only_provider_is_enabled_implicitly(self, db, monkeypatch):
        """A pre-UI (env-only) deployment stays working: enabled without a DB flag."""
        from app.core.config import settings

        _clear_env(monkeypatch)
        monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "env-id", raising=False)
        monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "env-secret", raising=False)
        _org(db).sso_config = {}
        db.flush()

        assert resolve_sso_config(db).google.ready is True

    def test_db_node_without_enabled_flag_is_not_ready(self, db, monkeypatch):
        """Saving credentials must not auto-enable a provider."""
        _clear_env(monkeypatch)
        _org(db).sso_config = {
            "google": {
                "client_id": {"value": "id", "secret": False},
                "client_secret": {"value": "sec", "secret": False},
            }
        }
        db.flush()

        assert resolve_sso_config(db).google.ready is False

    def test_ready_requires_enabled_and_all_fields(self, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        org = _org(db)
        org.sso_config = {
            "google": {
                "enabled": True,
                "client_id": {"value": "id", "secret": False},
                "client_secret": build_field_node("sec", True),
            }
        }
        db.flush()

        google = resolve_sso_config(db).google
        assert google.ready is True
        assert google.get("client_secret") == "sec"  # decrypted

        # Drop a required field → no longer ready.
        org.sso_config = {"google": {"enabled": True, "client_id": {"value": "id", "secret": False}}}
        db.flush()
        assert resolve_sso_config(db).google.ready is False

    def test_unreadable_secret_degrades_to_empty(self, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        _org(db).sso_config = {
            "google": {"enabled": True, "client_secret": build_field_node("sec", True)}
        }
        db.flush()
        _set_key(monkeypatch)  # rotate key → ciphertext no longer decryptable

        google = resolve_sso_config(db).google
        assert google.get("client_secret") == ""
        assert google.sources["client_secret"] == "none"


class TestGetSsoEndpoint:
    def test_requires_super_admin(self, client, db):
        _org(db)
        member = _create_user(db, "member", "get-mbr")
        client.cookies.update(_auth_cookie(member))
        assert client.get("/api/v1/settings/sso").status_code == 403

    def test_never_returns_secret_values(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        org = _org(db)
        org.sso_config = {
            "google": {
                "enabled": True,
                "client_id": {"value": "public-id", "secret": False},
                "client_secret": build_field_node("very-secret-value", True),
            }
        }
        db.flush()
        admin = _create_user(db, "super_admin", "get-sa")
        client.cookies.update(_auth_cookie(admin))

        body = client.get("/api/v1/settings/sso").json()
        assert body["google"]["client_id"] == "public-id"
        assert body["google"]["client_secret"]["configured"] is True
        assert body["google"]["client_secret"]["last4"] == "alue"
        # The plaintext secret appears nowhere in the response.
        assert "very-secret-value" not in client.get("/api/v1/settings/sso").text
        assert body["google"]["ready"] is True

    def test_exposes_redirect_uris_and_backend_url(self, client, db, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "BACKEND_PUBLIC_URL", "https://club.example", raising=False)
        _org(db)
        admin = _create_user(db, "super_admin", "get-uris")
        client.cookies.update(_auth_cookie(admin))

        body = client.get("/api/v1/settings/sso").json()
        assert body["backend_public_url"] == "https://club.example"
        assert (
            body["redirect_uris"]["google"]
            == "https://club.example/api/v1/auth/oauth/google/callback"
        )


class TestPutSsoEndpoint:
    def _admin(self, client, db, suffix):
        admin = _create_user(db, "super_admin", suffix)
        client.cookies.update(_auth_cookie(admin))
        return admin

    def test_encrypts_secret_before_persisting(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        org = _org(db)
        self._admin(client, db, "put-enc")

        resp = client.put(
            "/api/v1/settings/sso",
            json={"google": {"enabled": True, "client_id": "gid",
                             "client_secret": {"value": "topsecret"}}},
        )
        assert resp.status_code == 200
        stored = org.sso_config["google"]["client_secret"]
        assert stored["secret"] is True
        assert stored["value"] != "topsecret"  # ciphertext at rest
        assert secrets_crypto.decrypt(stored["value"]) == "topsecret"

    def test_blank_secret_leaves_prior_value(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        org = _org(db)
        self._admin(client, db, "put-blank")

        client.put("/api/v1/settings/sso",
                   json={"google": {"client_secret": {"value": "first"}}})
        # A second save that omits the secret must not wipe it.
        client.put("/api/v1/settings/sso", json={"google": {"enabled": True}})

        assert resolve_sso_config(db).google.get("client_secret") == "first"

    def test_clear_wipes_secret(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        org = _org(db)
        self._admin(client, db, "put-clear")

        client.put("/api/v1/settings/sso",
                   json={"google": {"client_secret": {"value": "first"}}})
        client.put("/api/v1/settings/sso",
                   json={"google": {"client_secret": {"clear": True}}})

        assert resolve_sso_config(db).google.configured("client_secret") is False

    def test_secret_write_rejected_without_key(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _force_no_key(monkeypatch)
        _org(db)
        self._admin(client, db, "put-nokey")

        resp = client.put(
            "/api/v1/settings/sso",
            json={"google": {"client_secret": {"value": "x"}}},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "sso_encryption_key_missing"

    def test_non_secret_field_saves_without_key(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _force_no_key(monkeypatch)
        _org(db)
        self._admin(client, db, "put-plain")

        resp = client.put("/api/v1/settings/sso", json={"google": {"client_id": "gid"}})
        assert resp.status_code == 200
        assert resolve_sso_config(db).google.get("client_id") == "gid"

    def test_requires_super_admin(self, client, db):
        _org(db)
        member = _create_user(db, "member", "put-mbr")
        client.cookies.update(_auth_cookie(member))
        assert client.put("/api/v1/settings/sso", json={"google": {"enabled": True}}).status_code == 403

    def test_writes_audit_without_secret_values(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        _org(db)
        self._admin(client, db, "put-audit")

        client.put("/api/v1/settings/sso",
                   json={"google": {"enabled": True, "client_secret": {"value": "topsecret"}}})

        entry = (
            db.query(AuditLog)
            .filter(AuditLog.table_name == "organization_settings", AuditLog.action == "update")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert entry is not None
        assert "sso_config.google.client_secret" in entry.changed_fields
        assert "topsecret" not in str(entry.changed_fields)
        assert entry.new_values is None

    def test_enabling_makes_providers_endpoint_report_ready(self, client, db, monkeypatch):
        _clear_env(monkeypatch)
        _set_key(monkeypatch)
        _org(db)
        self._admin(client, db, "put-ready")

        assert client.get("/api/v1/auth/sso/providers").json()["google"] is False

        client.put(
            "/api/v1/settings/sso",
            json={"google": {"enabled": True, "client_id": "gid",
                             "client_secret": {"value": "gsec"}}},
        )
        assert client.get("/api/v1/auth/sso/providers").json()["google"] is True

    def test_stored_secret_can_be_stored_plaintext_when_flagged(self, client, db, monkeypatch):
        """The per-field secret flag allows opting a field out of encryption."""
        _clear_env(monkeypatch)
        _clear_key(monkeypatch)  # no key, but secret=false must still save
        org = _org(db)
        self._admin(client, db, "put-plainsecret")

        resp = client.put(
            "/api/v1/settings/sso",
            json={"google": {"client_secret": {"value": "plainsec", "secret": False}}},
        )
        assert resp.status_code == 200
        stored = org.sso_config["google"]["client_secret"]
        assert stored["secret"] is False
        assert stored["value"] == "plainsec"  # stored as-is