"""Record a payment that arrived after a seat's receipt was cancelled

Revision ID: a3d9e2c71f48
Revises: f2c7a9e14b3d
Create Date: 2026-11-17

A member can have the gateway open while the sweep releases their seat. The gateway
then reports money that has moved for a receipt we had cancelled, and until now that
was stored as an ignored webhook event and nothing else. ``late_payment_at`` records
it on the seat, and ``late_payment_seen_at`` when an organiser acknowledged it, so the
club is shown every one it has not looked at yet.

Existing rows take NULL in both. Past late payments are not recoverable from here:
they are in the webhook event log and the gateway's dashboard, where they always were.
The downgrade drops both.
"""

import sqlalchemy as sa
from alembic import op

revision = "a3d9e2c71f48"
down_revision = "f2c7a9e14b3d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "registrations", sa.Column("late_payment_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "registrations", sa.Column("late_payment_seen_at", sa.DateTime(timezone=True))
    )


def downgrade() -> None:
    op.drop_column("registrations", "late_payment_seen_at")
    op.drop_column("registrations", "late_payment_at")
