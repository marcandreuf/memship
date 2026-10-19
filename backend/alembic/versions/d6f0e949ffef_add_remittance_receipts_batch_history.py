"""add remittance_receipts batch history

Records which receipts a batch carried, so the record survives the receipt
leaving it. `receipts.remittance_id` says which batch a receipt is in now, and
a returned receipt must leave its batch to be collected again — so a sent
batch's only record of what it sent was its frozen `receipt_count`, a number
with no names in it (#402).

Existing links are backfilled as still-held rows, dated from the batch rather
than from the migration. Receipts already released cannot be backfilled:
nothing recorded them, which is the gap this table closes going forward.

Revision ID: d6f0e949ffef
Revises: 60c569f93452
Create Date: 2026-10-19 04:06:46.203842
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6f0e949ffef'
down_revision: Union[str, None] = '60c569f93452'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'remittance_receipts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('remittance_id', sa.Integer(), nullable=False),
        sa.Column('receipt_id', sa.Integer(), nullable=False),
        sa.Column('amount_sent', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('released_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('release_reason', sa.String(length=30), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=True,
        ),
        sa.CheckConstraint(
            "release_reason IS NULL OR release_reason IN "
            "('reemitted', 'cancelled', 'paid_by_other_means', 'batch_cancelled')",
            name='valid_release_reason',
        ),
        sa.CheckConstraint(
            'amount_sent >= 0', name='remittance_receipt_amount_non_negative'
        ),
        sa.ForeignKeyConstraint(['receipt_id'], ['receipts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['remittance_id'], ['remittances.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('remittance_id', 'receipt_id', name='uq_remittance_receipt'),
    )
    op.create_index(
        op.f('ix_remittance_receipts_id'), 'remittance_receipts', ['id'], unique=False
    )
    op.create_index(
        'ix_remittance_receipts_receipt_id',
        'remittance_receipts',
        ['receipt_id'],
        unique=False,
    )
    op.create_index(
        'ix_remittance_receipts_remittance_id',
        'remittance_receipts',
        ['remittance_id'],
        unique=False,
    )

    # Every link that still exists, as a held row. `amount_sent` takes the
    # receipt's current total: for a receipt sitting in a batch those are the
    # same figure, and it is the best available answer for one whose amount
    # changed before the upgrade.
    op.execute(
        """
        INSERT INTO remittance_receipts
            (remittance_id, receipt_id, amount_sent, created_at)
        SELECT r.remittance_id, r.id, r.total_amount,
               COALESCE(rem.created_at, now())
        FROM receipts r
        JOIN remittances rem ON rem.id = r.remittance_id
        WHERE r.remittance_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index('ix_remittance_receipts_remittance_id', table_name='remittance_receipts')
    op.drop_index('ix_remittance_receipts_receipt_id', table_name='remittance_receipts')
    op.drop_index(op.f('ix_remittance_receipts_id'), table_name='remittance_receipts')
    op.drop_table('remittance_receipts')
