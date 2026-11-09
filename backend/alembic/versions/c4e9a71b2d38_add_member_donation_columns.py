"""Add the two columns a member-initiated donation needs

Revision ID: c4e9a71b2d38
Revises: b7e4d1a90c22
Create Date: 2026-11-09

``receipts.donation_self_service`` marks a receipt raised by the member pressing
Donate, as distinct from one an administrator raised by hand for a donation
already promised. The abandonment sweep has to tell them apart: the member's is
voided the day after it is due, and the administrator's is legitimately waiting
for a bank transfer and must be left alone. ``origin = 'donation'`` cannot carry
that, because ``ReceiptCreate`` accepts the origin and the admin route produces
it too (#434).

Nullable with no server default, so every existing receipt reads NULL and the
sweep's ``IS TRUE`` predicate matches nothing already recorded. Deliberately
absent from ``ReceiptCreate``, so the only writer is the donate endpoint.

``organization_settings.donation_message`` is the ask: a donation is not a
purchase, and the reason to give has to come from the organisation in its own
words rather than from a string we translate three ways.

The downgrade drops both. Losing the flag loses the ability to sweep, not a
record of money, and a dropped message is text an administrator can retype.
"""

import sqlalchemy as sa
from alembic import op

revision = "c4e9a71b2d38"
down_revision = "b7e4d1a90c22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "receipts",
        sa.Column("donation_self_service", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "organization_settings",
        sa.Column("donation_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("organization_settings", "donation_message")
    op.drop_column("receipts", "donation_self_service")
