"""The data rewrite in the gmail → smtp provider migration (#442).

The failure to guard against is mail breaking on upgrade: a screen-configured
Gmail account was pinned to Google's server, so after the rename it must still
be, whatever ``SMTP_HOST`` says.
"""

import importlib.util
from pathlib import Path

import pytest

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "b7c8d9e0f1a2_rename_gmail_mail_provider_to_smtp.py"
)


@pytest.fixture(scope="module")
def migration():
    spec = importlib.util.spec_from_file_location("gmail_to_smtp", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _field(value, secret=False):
    return {"value": value, "secret": secret}


def test_screen_configured_gmail_keeps_googles_endpoint(migration):
    config = {
        "active_provider": "gmail",
        "gmail": {"user": _field("club@gmail.com"), "app_password": _field("gAAAA", True)},
    }

    assert migration._gmail_to_smtp(config) is True

    assert config == {
        "active_provider": "smtp",
        "smtp": {
            "user": _field("club@gmail.com"),
            "password": _field("gAAAA", True),
            "host": _field("smtp.gmail.com"),
            "port": _field("587"),
            "tls": _field("true"),
        },
    }


def test_node_without_credentials_keeps_following_env(migration):
    """Such a node never pinned Google: its host came from SMTP_HOST, and still does."""
    config = {"gmail": {"from_email": _field("socios@club.example")}}

    migration._gmail_to_smtp(config)

    assert config == {"smtp": {"from_email": _field("socios@club.example")}}


def test_other_providers_are_untouched(migration):
    config = {"active_provider": "resend", "resend": {"api_key": _field("x", True)}}

    assert migration._gmail_to_smtp(config) is False
    assert config == {"active_provider": "resend", "resend": {"api_key": _field("x", True)}}


def test_downgrade_restores_the_old_shape(migration):
    config = {
        "active_provider": "gmail",
        "gmail": {"user": _field("club@gmail.com"), "app_password": _field("gAAAA", True)},
    }
    original = {k: dict(v) if isinstance(v, dict) else v for k, v in config.items()}

    migration._gmail_to_smtp(config)
    migration._smtp_to_gmail(config)

    assert config == original
