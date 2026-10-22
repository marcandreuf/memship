"""rename the gmail mail provider to smtp

The `gmail` provider was always a generic SMTP transport, with its host, port
and TLS flag pinned to Google's for screen-configured accounts and read from
`.env` otherwise. It becomes one `smtp` provider whose host, port and TLS are
stored fields, with Gmail as a preset in the settings screen (#442).

A stored `gmail` node moves to `smtp`, and `app_password` becomes `password`.
When the node holds an account or a password, the transport was pinned to
Google, so Google's endpoint is written in explicitly: without it the host
would fall back to `SMTP_HOST`, and an install with a different server there
would quietly start dialling it. A node with neither kept using `.env` and
still does. An `active_provider` of `gmail` follows the rename.

The `gmail` health row is dropped: it was recorded against the old field set,
so it could never match the new fingerprint, and the provider starts as
unverified. That does not deactivate it — only switching to a provider is
gated on a passing send.

The downgrade renames back and drops the stored host, port and TLS, which the
old provider could not hold.

Revision ID: b7c8d9e0f1a2
Revises: e3f4a5b6c7d8
Create Date: 2026-10-22 16:00:00.000000
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, None] = 'e3f4a5b6c7d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GMAIL_ENDPOINT = {
    "host": {"value": "smtp.gmail.com", "secret": False},
    "port": {"value": "587", "secret": False},
    "tls": {"value": "true", "secret": False},
}


def _has_value(node: dict, name: str) -> bool:
    field = node.get(name)
    return isinstance(field, dict) and bool(field.get("value"))


def _rewrite(rename) -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT mailing_config FROM organization_settings WHERE id = 1")
    ).first()
    if row is None or not row[0]:
        return
    config = dict(row[0])
    if rename(config):
        conn.execute(
            sa.text(
                "UPDATE organization_settings SET mailing_config = CAST(:config AS jsonb) "
                "WHERE id = 1"
            ),
            {"config": json.dumps(config)},
        )


def _gmail_to_smtp(config: dict) -> bool:
    changed = False
    if "gmail" in config:
        node = dict(config.pop("gmail") or {})
        if "app_password" in node:
            node["password"] = node.pop("app_password")
        if _has_value(node, "user") or _has_value(node, "password"):
            for name, field in GMAIL_ENDPOINT.items():
                node.setdefault(name, field)
        config["smtp"] = node
        changed = True
    if config.get("active_provider") == "gmail":
        config["active_provider"] = "smtp"
        changed = True
    return changed


def _smtp_to_gmail(config: dict) -> bool:
    changed = False
    if "smtp" in config:
        node = dict(config.pop("smtp") or {})
        for name in GMAIL_ENDPOINT:
            node.pop(name, None)
        if "password" in node:
            node["app_password"] = node.pop("password")
        config["gmail"] = node
        changed = True
    if config.get("active_provider") == "smtp":
        config["active_provider"] = "gmail"
        changed = True
    return changed


def upgrade() -> None:
    _rewrite(_gmail_to_smtp)
    op.execute("DELETE FROM mail_transport_health WHERE provider = 'gmail'")


def downgrade() -> None:
    _rewrite(_smtp_to_gmail)
    op.execute("DELETE FROM mail_transport_health WHERE provider = 'smtp'")
