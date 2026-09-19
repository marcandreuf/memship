"""Separate who could be emailed from who was

Revision ID: 20f5b7a3c3f3
Revises: c58bc5181d90
Create Date: 2026-09-19

``announcement_recipients.emailed`` was written once, at send time, from the
member's *eligibility*: they had an address and had not opted out. Nothing ever
revisited it with what the fan-out managed. The column comment said "email
actually sent", the model docstring said it mirrored the opt-out, and the API
called it ``emailed_count`` — three statements, two meanings (#228).

On an install with no mail transport, which is a fresh one before a provider is
configured, an admin who broadcast to the whole club was told every member had
been emailed and none had. The same gap covers any per-recipient failure: a
bounce, a rejected address, a transport error part-way through the fan-out.

So the column is renamed to what it has always held, and a second one records
the outcome:

- ``email_eligible`` — the audience snapshot, unchanged in meaning and in data.
- ``email_sent`` — False when the fan-out is about to try, True once the
  transport accepts it.

``email_sent`` is nullable, and existing rows keep NULL on purpose. Their
outcome was never recorded and backfilling from ``email_eligible`` would
restate the very claim this fixes; writing False would assert a failure that
may not have happened. NULL reads as "not recorded", and the stats endpoint
reports it as unknown rather than as zero delivered.

The rename is in-place, so no data moves and the index on ``announcement_id``
is untouched.
"""

from alembic import op
import sqlalchemy as sa

revision = "20f5b7a3c3f3"
down_revision = "c58bc5181d90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "announcement_recipients",
        "emailed",
        new_column_name="email_eligible",
    )
    op.add_column(
        "announcement_recipients",
        sa.Column("email_sent", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    # The outcome has nowhere to go in the old shape — one column cannot hold
    # both facts, which is what this migration exists to undo. Dropping it
    # loses the delivery record; the eligibility snapshot survives intact.
    op.drop_column("announcement_recipients", "email_sent")
    op.alter_column(
        "announcement_recipients",
        "email_eligible",
        new_column_name="emailed",
    )
