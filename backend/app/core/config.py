"""Application settings via pydantic-settings."""

import os
import subprocess
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _read_version() -> str:
    # Git tags are the single source of truth for the version (there is no VERSION
    # file). Images bake the tag in as APP_VERSION at build time; running from source
    # falls back to `git describe`.
    env_version = os.environ.get("APP_VERSION", "").strip()
    if env_version:
        return env_version

    try:
        described = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        ).stdout.strip()
        if described:
            return described.lstrip("v")
    except (subprocess.SubprocessError, OSError):
        pass

    return "0.0.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    DATABASE_URL: str = "postgresql://memship:memship@localhost:5433/memship_db"
    DATABASE_TEST_URL: str = "postgresql://memship:memship@localhost:5434/memship_test_db"

    # Security
    # Signs the session JWT, the member-card QR HMAC and the OAuth state cookie,
    # and derives the key that encrypts stored payment-provider credentials.
    # Leave it empty outside development and a per-install key is generated and
    # persisted to SESSION_KEY_FILE — see _resolve_session_secret below. A known
    # placeholder is treated as empty, so a copied compose file cannot ship a
    # published signing key.
    SECRET_KEY: str = "change-me-in-production"
    # Where the auto-generated signing key is persisted. Empty →
    # "<STORAGE_LOCAL_PATH>/session.key". Must sit on a PERSISTENT volume: losing
    # it logs everyone out AND makes stored payment-provider secrets unreadable.
    SESSION_KEY_FILE: str = ""
    # Force the Secure attribute on the session cookie on/off. Empty → derived
    # from the FRONTEND_URL scheme (see session_cookie_secure).
    COOKIE_SECURE: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    # Fernet key (urlsafe base64, 32 bytes) used to encrypt provider secrets stored
    # in the DB via the SSO settings screen. Optional OVERRIDE: when set (e.g. from a
    # secrets manager) it wins. When empty, the app auto-generates a per-install key
    # and persists it to SECRETS_KEY_FILE (never the database), so a DB dump alone
    # cannot decrypt the stored secrets. Generate one explicitly with:
    #   python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
    MEMSHIP_SECRET_KEY: str = ""
    # Where the auto-generated encryption key is stored when MEMSHIP_SECRET_KEY is
    # unset. Empty → "<STORAGE_LOCAL_PATH>/secret.key". Must sit on a PERSISTENT
    # volume so the key survives restarts (otherwise stored secrets become unreadable).
    SECRETS_KEY_FILE: str = ""

    # Application
    APP_ENV: str = "development"
    APP_VERSION: str = _read_version()
    DEFAULT_LOCALE: str = "es"
    # Mail domain for the members `seed --demo` creates. The default is an
    # RFC 2606 reserved TLD, so nothing it generates can ever be delivered —
    # which is what you want everywhere except an environment that deliberately
    # sends real mail. Point it at a domain you own with catch-all receiving to
    # make the demo club's members reachable.
    SEED_EMAIL_DOMAIN: str = "mediterrani.example"
    CORS_ORIGINS: str = "http://localhost:3000"
    LOG_LEVEL: str = "info"

    # SMTP (optional — emails disabled if SMTP_HOST is empty).
    # Real credentials belong in backend/.env (gitignored), never here — this
    # file is committed to a public repo.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@memship.local"
    SMTP_TLS: bool = True
    FRONTEND_URL: str = "http://localhost:3000"
    # Publicly reachable backend URL — used for provider callbacks (e.g. Redsys
    # `Ds_Merchant_MerchantURL`). In dev this is the Docker API port; in prod
    # it must be the external hostname that the payment gateway can POST to.
    BACKEND_PUBLIC_URL: str = "http://localhost:8003"

    # Resend (optional — alternative to SMTP for managed email delivery)
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = ""

    # Single sign-on (optional — a provider is offered only when configured)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # Apple: APPLE_CLIENT_ID is the Services ID (not the App ID). APPLE_PRIVATE_KEY
    # is the contents of the .p8 key file — newlines may be given as literal \n.
    APPLE_CLIENT_ID: str = ""
    APPLE_TEAM_ID: str = ""
    APPLE_KEY_ID: str = ""
    APPLE_PRIVATE_KEY: str = ""

    # Celery / Redis
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"

    # File storage
    STORAGE_LOCAL_PATH: str = "storage"
    MAX_UPLOAD_SIZE_MB: int = 10

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    @property
    def session_cookie_secure(self) -> bool:
        """Whether the session cookie carries ``Secure``.

        Derived from ``FRONTEND_URL``: the cookie is only ever sent to that
        origin, so its scheme is the authoritative answer — and it is already
        correct on every install, because ``scripts/install.sh --domain`` writes
        the https URL there. ``COOKIE_SECURE`` overrides it for a setup that
        terminates TLS somewhere the app cannot see.
        """
        override = self.COOKIE_SECURE.strip().lower()
        if override:
            return override in ("1", "true", "yes", "on")
        return self.FRONTEND_URL.strip().lower().startswith("https://")

    @property
    def google_sso_enabled(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET)

    @property
    def apple_sso_enabled(self) -> bool:
        return bool(
            self.APPLE_CLIENT_ID
            and self.APPLE_TEAM_ID
            and self.APPLE_KEY_ID
            and self.APPLE_PRIVATE_KEY
        )

    @property
    def apple_private_key_pem(self) -> str:
        """The .p8 key with escaped newlines restored to real ones."""
        return self.APPLE_PRIVATE_KEY.replace("\\n", "\n").strip()

    @property
    def sso_enabled(self) -> bool:
        return self.google_sso_enabled or self.apple_sso_enabled

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


settings = Settings()


# Every placeholder SECRET_KEY that has ever shipped in this repo. They are
# public, so anything signed with one is forgeable: a session cookie for user 1
# (super admin), a member-card QR, and the Fernet key over stored payment
# credentials. Treated as "no key configured" rather than as a key.
PLACEHOLDER_SECRET_KEYS = frozenset(
    {
        "change-me-in-production",
        "dev-secret-key-change-in-production",
        "change-me-in-production-use-a-random-64-char-string",
    }
)


def _session_key_file() -> Path:
    if settings.SESSION_KEY_FILE:
        return Path(settings.SESSION_KEY_FILE)
    return Path(settings.STORAGE_LOCAL_PATH) / "session.key"


def _persisted_session_secret() -> str:
    """Read the per-install signing key, minting it on first boot.

    Created with O_CREAT|O_EXCL and then read back, so the API and the two Celery
    processes racing on a cold start converge on whichever one won rather than
    each keeping its own key.

    Falls back to a process-local random key when the file can be neither read
    nor written. That still beats a published constant, but sessions then break
    on every restart — hence the error log.
    """
    import logging
    import os
    import secrets

    path = _session_key_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(secrets.token_hex(32))
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    except OSError as e:
        logging.getLogger(__name__).error(
            "Cannot persist the session signing key to %s (%s). Falling back to a "
            "process-local key: every restart will log all users out and stored "
            "payment-provider credentials will not decrypt. Set SECRET_KEY "
            "explicitly, or put SESSION_KEY_FILE on a writable volume.",
            path,
            e,
        )
    return secrets.token_hex(32)


def _resolve_session_secret() -> None:
    configured = settings.SECRET_KEY.strip()
    if configured and configured not in PLACEHOLDER_SECRET_KEYS:
        return

    if settings.APP_ENV == "development":
        # Keep the placeholder in dev: tests and fixtures want a stable key and
        # nothing there is worth forging.
        settings.SECRET_KEY = configured or "change-me-in-production"
        return

    settings.SECRET_KEY = _persisted_session_secret()


_resolve_session_secret()
