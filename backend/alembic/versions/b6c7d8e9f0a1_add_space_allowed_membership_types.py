"""add_space_allowed_membership_types

Lets a club keep a space for particular membership types, the way an activity
already restricts registration. The column is the same shape as
``activities.allowed_membership_types``: an integer array of membership type
ids, NULL or empty meaning the space is open to every member.

Every existing space keeps NULL, so nothing that is bookable today stops being
bookable.

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
Create Date: 2026-09-07 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b6c7d8e9f0a1'
down_revision: Union[str, None] = 'a5b6c7d8e9f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'spaces',
        sa.Column(
            'allowed_membership_types',
            postgresql.ARRAY(sa.Integer()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('spaces', 'allowed_membership_types')
