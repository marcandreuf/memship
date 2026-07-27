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
    SECRET_KEY: str = "change-me-in-production"
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
    CORS_ORIGINS: str = "http://localhost:3000"

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
    def smtp_enabled(self) -> bool:
        return bool(self.SMTP_HOST)

    @property
    def email_enabled(self) -> bool:
        return bool(self.RESEND_API_KEY) or bool(self.SMTP_HOST)

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
