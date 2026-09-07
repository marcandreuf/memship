"""add receipt purchased membership type

Records which plan a purchase receipt was raised for, so that activation can
read it off the receipt it has just marked paid. A member must not move tiers
until the money arrives, which means the pending purchase has to be remembered
somewhere, and the receipt is the row that already knows when it is paid.

``ON DELETE SET NULL``, matching ``members.membership_type_id`` — the only other
foreign key to this table, and the one that settles the question of whether a
membership type is a row the schema expects to survive losing. The API only ever
soft-deletes one (``DELETE /membership-types/{id}`` sets ``is_active = false``),
but a plain restricting key would turn any future hard delete into a foreign key
violation on a receipt, which is exactly the trap the booking column avoided. A
receipt outlives the plan and keeps its description and its amount, which is
what the member was actually invoiced for.

The column is nullable and every existing row stays NULL, so this migration
changes nothing until the purchase flow exists.

Revision ID: 01ea89383f1d
Revises: c6d7e8f9a0b1
Create Date: 2026-09-07 10:35:42.954905
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '01ea89383f1d'
down_revision: Union[str, None] = 'c6d7e8f9a0b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'receipts',
        sa.Column('purchased_membership_type_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_receipts_purchased_membership_type_id',
        'receipts',
        'membership_types',
        ['purchased_membership_type_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_receipts_purchased_membership_type_id', 'receipts', type_='foreignkey'
    )
    op.drop_column('receipts', 'purchased_membership_type_id')
