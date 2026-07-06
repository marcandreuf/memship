"""add_member_numbering_config_to_organization_settings

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-07-06 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'organization_settings',
        sa.Column('member_number_prefix', sa.String(length=20), nullable=False, server_default=''),
    )
    op.add_column(
        'organization_settings',
        sa.Column('member_number_padding', sa.SmallInteger(), nullable=False, server_default='4'),
    )
    op.add_column(
        'organization_settings',
        sa.Column('member_number_next', sa.Integer(), nullable=False, server_default='1'),
    )


def downgrade() -> None:
    op.drop_column('organization_settings', 'member_number_next')
    op.drop_column('organization_settings', 'member_number_padding')
    op.drop_column('organization_settings', 'member_number_prefix')
