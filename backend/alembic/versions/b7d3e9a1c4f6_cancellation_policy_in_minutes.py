"""Cancellation policy for paid seats: deadlines in minutes, a mode past the deadline

Revision ID: b7d3e9a1c4f6
Revises: a4c1d8e92b57
Create Date: 2026-11-26

An activity's ``self_cancellation_deadline_hours`` becomes
``self_cancellation_deadline_minutes`` and the club-wide
``features.booking_cancellation_deadline_hours`` becomes
``booking_cancellation_deadline_minutes``, so "cancel less than 30 minutes before
and lose the payment" can be expressed (#604). Values are multiplied by 60; a
NULL deadline stays NULL, which still means no deadline.

``late_cancellation_mode`` says what happens past the deadline. Every existing
row gets ``block``, which is what the product did, so nothing changes until a
club chooses otherwise.

A space gets its own ``cancellation_deadline_minutes``, NULL for every existing
space: it inherits the club default, as ``auto_cancel_*`` does, so each space
keeps the deadline it had.

The downgrade rounds minutes up to whole hours, so a deadline is never shorter
than it was set; the mode is lost.
"""

from alembic import op
import sqlalchemy as sa

revision = "b7d3e9a1c4f6"
down_revision = "a4c1d8e92b57"
branch_labels = None
depends_on = None

OLD_KEY = "booking_cancellation_deadline_hours"
NEW_KEY = "booking_cancellation_deadline_minutes"


def upgrade() -> None:
    op.add_column(
        "activities", sa.Column("self_cancellation_deadline_minutes", sa.Integer())
    )
    op.execute(
        "UPDATE activities SET self_cancellation_deadline_minutes = "
        "self_cancellation_deadline_hours * 60 "
        "WHERE self_cancellation_deadline_hours IS NOT NULL"
    )
    op.drop_column("activities", "self_cancellation_deadline_hours")
    for table in ("activities", "spaces"):
        op.add_column(
            table,
            sa.Column(
                "late_cancellation_mode",
                sa.String(20),
                nullable=False,
                server_default="block",
            ),
        )
    op.add_column("spaces", sa.Column("cancellation_deadline_minutes", sa.Integer()))

    op.create_check_constraint(
        "valid_activity_late_cancellation_mode",
        "activities",
        "late_cancellation_mode IN ('block', 'allow_no_refund')",
    )
    op.create_check_constraint(
        "activity_cancellation_deadline_non_negative",
        "activities",
        "self_cancellation_deadline_minutes IS NULL OR self_cancellation_deadline_minutes >= 0",
    )
    op.create_check_constraint(
        "valid_space_late_cancellation_mode",
        "spaces",
        "late_cancellation_mode IN ('block', 'allow_no_refund')",
    )
    op.create_check_constraint(
        "space_cancellation_deadline_non_negative",
        "spaces",
        "cancellation_deadline_minutes IS NULL OR cancellation_deadline_minutes >= 0",
    )

    # features is a sparse JSON object; only a stored integer is converted. An
    # invalid stored value is dropped so the reader falls back to the default,
    # as it already did for the old key.
    op.execute(
        f"""
        UPDATE organization_settings
        SET features = (features - '{OLD_KEY}')
            || CASE
                 WHEN jsonb_typeof(features -> '{OLD_KEY}') = 'number'
                      AND (features ->> '{OLD_KEY}') ~ '^[0-9]+$'
                 THEN jsonb_build_object(
                        '{NEW_KEY}',
                        LEAST((features ->> '{OLD_KEY}')::bigint * 60, 525600)
                      )
                 ELSE '{{}}'::jsonb
               END
        WHERE features ? '{OLD_KEY}'
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        UPDATE organization_settings
        SET features = (features - '{NEW_KEY}')
            || CASE
                 WHEN jsonb_typeof(features -> '{NEW_KEY}') = 'number'
                      AND (features ->> '{NEW_KEY}') ~ '^[0-9]+$'
                 THEN jsonb_build_object(
                        '{OLD_KEY}',
                        LEAST(((features ->> '{NEW_KEY}')::bigint + 59) / 60, 8760)
                      )
                 ELSE '{{}}'::jsonb
               END
        WHERE features ? '{NEW_KEY}'
        """
    )
    op.drop_constraint("space_cancellation_deadline_non_negative", "spaces")
    op.drop_constraint("valid_space_late_cancellation_mode", "spaces")
    op.drop_constraint("activity_cancellation_deadline_non_negative", "activities")
    op.drop_constraint("valid_activity_late_cancellation_mode", "activities")
    op.drop_column("spaces", "cancellation_deadline_minutes")
    op.drop_column("spaces", "late_cancellation_mode")
    op.add_column(
        "activities", sa.Column("self_cancellation_deadline_hours", sa.Integer())
    )
    op.execute(
        "UPDATE activities SET self_cancellation_deadline_hours = "
        "(self_cancellation_deadline_minutes + 59) / 60 "
        "WHERE self_cancellation_deadline_minutes IS NOT NULL"
    )
    op.drop_column("activities", "late_cancellation_mode")
    op.drop_column("activities", "self_cancellation_deadline_minutes")
