"""The signing key must never be one of the placeholders shipped in the repo.

``SECRET_KEY`` signs the session JWT, the member-card QR HMAC and the OAuth state
cookie, and derives the Fernet key over stored payment-provider credentials. The
compose files used to hand one of three published constants to every deployment,
so anyone could mint a super-admin session on any of them.
"""

import pytest

from app.core.config import (
    PLACEHOLDER_SECRET_KEYS,
    Settings,
    _resolve_session_secret,
)


@pytest.fixture
def resolve(tmp_path, monkeypatch):
    """Run the resolution against a throwaway Settings and storage root."""

    def run(secret_key: str, app_env: str = "production") -> Settings:
        import app.core.config as config

        probe = Settings(
            SECRET_KEY=secret_key,
            APP_ENV=app_env,
            STORAGE_LOCAL_PATH=str(tmp_path),
            SESSION_KEY_FILE="",
        )
        monkeypatch.setattr(config, "settings", probe)
        _resolve_session_secret()
        return probe

    return run


@pytest.mark.parametrize("placeholder", sorted(PLACEHOLDER_SECRET_KEYS))
def test_placeholders_are_replaced_in_production(resolve, placeholder):
    settings = resolve(placeholder)

    assert settings.SECRET_KEY not in PLACEHOLDER_SECRET_KEYS
    assert len(settings.SECRET_KEY) >= 32


def test_blank_key_is_replaced_in_production(resolve):
    settings = resolve("")

    assert len(settings.SECRET_KEY) >= 32


def test_an_operator_supplied_key_is_left_alone(resolve):
    settings = resolve("a-real-key-nobody-else-has")

    assert settings.SECRET_KEY == "a-real-key-nobody-else-has"


def test_the_generated_key_is_persisted_and_reused(resolve, tmp_path):
    first = resolve("").SECRET_KEY
    second = resolve("").SECRET_KEY

    assert first == second
    assert (tmp_path / "session.key").read_text().strip() == first


def test_development_keeps_the_placeholder(resolve, tmp_path):
    """Fixtures and tests want a stable key, and nothing local is worth forging."""
    settings = resolve("change-me-in-production", app_env="development")

    assert settings.SECRET_KEY == "change-me-in-production"
    assert not (tmp_path / "session.key").exists()
