"""Add users.sessions_valid_from

Revision ID: 8d2f3e4a5b6c
Revises: 7c1e2d3f4a5b
Create Date: 2026-09-21

A session token was valid until its own expiry, and `/auth/refresh` re-issues
one to any caller whose token is still valid — so a session opened with a
password that has since been reset stayed alive for as long as it kept being
used. Whoever had the old password kept the access the reset was meant to end.

The column records the instant before which no token is honoured. A password
reset sets it; the auth dependencies compare it with the token's `iat`. NULL
means no reset has happened and every token is judged on its expiry alone,
which is what every existing row gets.
"""

import sqlalchemy as sa
from alembic import op

revision = "8d2f3e4a5b6c"
down_revision = "7c1e2d3f4a5b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("sessions_valid_from", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "sessions_valid_from")
