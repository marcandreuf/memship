"""merge_sso_mailing_and_profile_fields_heads

Revision ID: 120971684ed2
Revises: b3c4d5e6f7a8, f0a1b2c3d4e5
Create Date: 2026-07-21 23:55:13.011916
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '120971684ed2'
down_revision: Union[str, None] = ('b3c4d5e6f7a8', 'f0a1b2c3d4e5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
