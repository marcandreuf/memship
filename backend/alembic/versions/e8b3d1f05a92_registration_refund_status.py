"""Record on a registration whether its payment is owed back

Revision ID: e8b3d1f05a92
Revises: d5a2c8e41f67
Create Date: 2026-11-17

``registrations.refund_status`` is ``none``, ``due`` or ``returned``. Cancelling a seat
whose receipt is paid sets ``due`` unless the organiser keeps the payment, and the
organiser lists the ``due`` ones and marks each ``returned`` once the money is back,
recording who, when and, optionally, the credit note issued for it.

It is a property of the seat rather than something read off the receipt, so that a
payment the club decides to keep is not listed as owed.

Existing rows take ``none``, including cancelled registrations with a paid receipt:
they predate the marking, and the club has already settled them offline. Back-filling
them would list every past cancellation as a debt.

The downgrade drops the columns, losing the record of which refunds were made. That
record is also in the gateway's own dashboard, where the money was returned.
"""

import sqlalchemy as sa
from alembic import op

revision = "e8b3d1f05a92"
down_revision = "d5a2c8e41f67"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "registrations",
        sa.Column(
            "refund_status", sa.String(length=20), nullable=False, server_default="none"
        ),
    )
    op.add_column(
        "registrations",
        sa.Column("refund_returned_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "registrations",
        sa.Column(
            "refund_returned_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
    )
    op.add_column(
        "registrations",
        sa.Column("refund_credit_note_id", sa.Integer()),
    )
    op.create_foreign_key(
        "fk_registrations_refund_credit_note_id",
        "registrations",
        "receipts",
        ["refund_credit_note_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "valid_registration_refund_status",
        "registrations",
        "refund_status IN ('none', 'due', 'returned')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "valid_registration_refund_status", "registrations", type_="check"
    )
    op.drop_constraint(
        "fk_registrations_refund_credit_note_id", "registrations", type_="foreignkey"
    )
    op.drop_column("registrations", "refund_credit_note_id")
    op.drop_column("registrations", "refund_returned_by")
    op.drop_column("registrations", "refund_returned_at")
    op.drop_column("registrations", "refund_status")
