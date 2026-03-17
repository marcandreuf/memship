"""Application settings via pydantic-settings."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _read_version() -> str:
    # Search upward from this file for VERSION
    current = Path(__file__).resolve().parent
    while current != current.parent:
        version_file = current / "VERSION"
        if version_file.exists():
            return version_file.read_text().strip()
        current = current.parent
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

    # Application
    APP_ENV: str = "development"
    APP_VERSION: str = _read_version()
    DEFAULT_LOCALE: str = "es"
    CORS_ORIGINS: str = "http://localhost:3000"

    # SMTP (optional — emails disabled if SMTP_HOST is empty)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@memship.local"
    SMTP_TLS: bool = True
    FRONTEND_URL: str = "http://localhost:3000"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.SMTP_HOST)

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


settings = Settings()
