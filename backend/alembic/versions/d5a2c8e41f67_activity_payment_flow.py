"""Add the payment flow, accepted methods and auto-cancel settings to activities

Revision ID: d5a2c8e41f67
Revises: c4e9a71b2d38
Create Date: 2026-11-17

``activities.payment_flow`` says how an activity treats payment: ``legacy`` confirms
a registration at once and bills it afterwards, ``pay_to_confirm`` holds the seat as
``pending`` until the receipt is paid. It is an explicit column rather than a reading
of "no methods set", because a free activity has no methods and would read as legacy.

Every activity that exists when this runs is stamped ``legacy``, so nothing already
running changes behaviour. The server default is then switched to ``pay_to_confirm``,
so every activity created from here on uses the new flow. The column is never edited
afterwards; ``legacy`` exists only so installs with activities in flight keep working.

``payment_methods`` is the set a member may pay with (card, bizum, transfer, cash),
``auto_cancel_enabled`` / ``auto_cancel_hours`` override the club's default and are NULL
to inherit it, and ``registrations.payment_due_at`` is the deadline of a pending seat.

The downgrade drops the columns. Nothing reads them before the code that writes them
ships, so no record of money is lost.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d5a2c8e41f67"
down_revision = "c4e9a71b2d38"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "activities",
        sa.Column(
            "payment_flow", sa.String(length=20), nullable=False, server_default="legacy"
        ),
    )
    op.alter_column("activities", "payment_flow", server_default="pay_to_confirm")
    op.add_column(
        "activities",
        sa.Column(
            "payment_methods",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column("activities", sa.Column("auto_cancel_enabled", sa.Boolean()))
    op.add_column("activities", sa.Column("auto_cancel_hours", sa.Integer()))
    op.create_check_constraint(
        "valid_activity_payment_flow",
        "activities",
        "payment_flow IN ('legacy', 'pay_to_confirm')",
    )
    op.create_check_constraint(
        "valid_activity_payment_methods",
        "activities",
        "payment_methods <@ ARRAY['card', 'bizum', 'transfer', 'cash']::varchar[]",
    )
    op.add_column(
        "registrations",
        sa.Column("payment_due_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_column("registrations", "payment_due_at")
    op.drop_constraint("valid_activity_payment_methods", "activities", type_="check")
    op.drop_constraint("valid_activity_payment_flow", "activities", type_="check")
    op.drop_column("activities", "auto_cancel_hours")
    op.drop_column("activities", "auto_cancel_enabled")
    op.drop_column("activities", "payment_methods")
    op.drop_column("activities", "payment_flow")
