"""Support the sweep that cancels pending seats left unpaid

Revision ID: f2c7a9e14b3d
Revises: e8b3d1f05a92
Create Date: 2026-11-17

``payment_reminder_sent_at`` records that the member was warned before the deadline,
so the hourly sweep warns once. ``cancelled_cause`` is ``payment_expired`` when the
sweep cancelled the seat, so the organiser can tell it from a cancellation a person
made; NULL for every other one. The partial index serves the sweep's query, which
reads only pending rows by deadline.

Existing rows take NULL in both, which is what they are: none was ever reminded or
expired by a sweep that did not exist. The downgrade drops all three.
"""

import sqlalchemy as sa
from alembic import op

revision = "f2c7a9e14b3d"
down_revision = "e8b3d1f05a92"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "registrations",
        sa.Column("payment_reminder_sent_at", sa.DateTime(timezone=True)),
    )
    op.add_column("registrations", sa.Column("cancelled_cause", sa.String(length=30)))
    op.create_check_constraint(
        "valid_registration_cancelled_cause",
        "registrations",
        "cancelled_cause IN ('payment_expired')",
    )
    op.create_index(
        "idx_registrations_pending_due",
        "registrations",
        ["payment_due_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("idx_registrations_pending_due", table_name="registrations")
    op.drop_constraint(
        "valid_registration_cancelled_cause", "registrations", type_="check"
    )
    op.drop_column("registrations", "cancelled_cause")
    op.drop_column("registrations", "payment_reminder_sent_at")
