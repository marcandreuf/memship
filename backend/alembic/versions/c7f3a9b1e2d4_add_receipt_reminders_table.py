"""add_receipt_reminders_table

Revision ID: c7f3a9b1e2d4
Revises: fe0fc0bd21e5
Create Date: 2026-06-11 12:40:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c7f3a9b1e2d4'
down_revision: Union[str, None] = 'fe0fc0bd21e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('receipt_reminders',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('receipt_id', sa.Integer(), nullable=False),
    sa.Column('reminder_number', sa.Integer(), nullable=False),
    sa.Column('channel', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('to_email', sa.String(length=255), nullable=True),
    sa.Column('triggered_by', sa.String(length=20), nullable=False),
    sa.Column('triggered_by_user_id', sa.Integer(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('sent_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.CheckConstraint("channel IN ('email')", name='valid_receipt_reminder_channel'),
    sa.CheckConstraint("status IN ('sent', 'failed', 'skipped')", name='valid_receipt_reminder_status'),
    sa.CheckConstraint("triggered_by IN ('scheduled', 'manual')", name='valid_receipt_reminder_triggered_by'),
    sa.ForeignKeyConstraint(['receipt_id'], ['receipts.id'], ),
    sa.ForeignKeyConstraint(['triggered_by_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_receipt_reminders_id'), 'receipt_reminders', ['id'], unique=False)
    op.create_index('ix_receipt_reminders_receipt', 'receipt_reminders', ['receipt_id', 'sent_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_receipt_reminders_receipt', table_name='receipt_reminders')
    op.drop_index(op.f('ix_receipt_reminders_id'), table_name='receipt_reminders')
    op.drop_table('receipt_reminders')
