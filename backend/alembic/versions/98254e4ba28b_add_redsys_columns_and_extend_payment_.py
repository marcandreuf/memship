"""add_redsys_columns_and_extend_payment_method_check

Revision ID: 98254e4ba28b
Revises: 31484ce4ff84
Create Date: 2026-04-23 17:50:33.900218
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '98254e4ba28b'
down_revision: Union[str, None] = '31484ce4ff84'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('receipts', sa.Column('redsys_ds_order', sa.String(length=12), nullable=True))
    op.add_column('receipts', sa.Column('redsys_auth_code', sa.String(length=8), nullable=True))
    op.create_unique_constraint('uq_receipts_redsys_ds_order', 'receipts', ['redsys_ds_order'])

    op.drop_constraint('valid_payment_method', 'receipts', type_='check')
    op.create_check_constraint(
        'valid_payment_method',
        'receipts',
        "payment_method IN ('cash', 'bank_transfer', 'card', 'direct_debit', "
        "'stripe_checkout', 'redsys', 'bizum') OR payment_method IS NULL",
    )


def downgrade() -> None:
    op.drop_constraint('valid_payment_method', 'receipts', type_='check')
    op.create_check_constraint(
        'valid_payment_method',
        'receipts',
        "payment_method IN ('cash', 'bank_transfer', 'card', 'direct_debit', "
        "'stripe_checkout') OR payment_method IS NULL",
    )

    op.drop_constraint('uq_receipts_redsys_ds_order', 'receipts', type_='unique')
    op.drop_column('receipts', 'redsys_auth_code')
    op.drop_column('receipts', 'redsys_ds_order')
