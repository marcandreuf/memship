"""add_member_membership_reversion

Records where a paid tier went when a membership fee went unpaid, so it can be
given back when the fee is settled.

``members.membership_type_id`` is overwritten by the reversion, which destroys
the one fact restoring the plan needs: which plan it was. Everything else about
a lapse is derived from the receipt's own dates, so these two columns are the
whole of the new stored state.

``ON DELETE SET NULL`` mirrors ``membership_type_id`` itself: a club deleting a
plan while somebody is lapsed leaves that member on the free tier with nothing
to restore, rather than blocking the delete on a member who is not even on the
plan any more.

Both columns are nullable and every existing row stays NULL, which reads as "has
not lapsed" — this migration changes no behaviour on its own. Reversion is off
until ``membership_lapse_enabled`` is switched on.

Revision ID: e7f8a9b0c1d2
Revises: 01ea89383f1d
Create Date: 2026-09-07 20:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, None] = '01ea89383f1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'members',
        sa.Column('membership_reverted_from_id', sa.Integer(), nullable=True),
    )
    op.add_column(
        'members',
        sa.Column(
            'membership_reverted_at', sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.create_foreign_key(
        'fk_members_membership_reverted_from_id',
        'members',
        'membership_types',
        ['membership_reverted_from_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_members_membership_reverted_from_id', 'members', type_='foreignkey'
    )
    op.drop_column('members', 'membership_reverted_at')
    op.drop_column('members', 'membership_reverted_from_id')
