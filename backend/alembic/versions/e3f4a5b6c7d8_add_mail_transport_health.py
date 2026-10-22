"""add mail_transport_health

Records the outcome of the last send through each mail provider, against a
fingerprint of the credentials it used, so the settings screen can tell a
credential that works from one that was never tried or has started failing
(#338).

Revision ID: e3f4a5b6c7d8
Revises: d6f0e949ffef
Create Date: 2026-10-22 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3f4a5b6c7d8'
down_revision: Union[str, None] = 'd6f0e949ffef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'mail_transport_health',
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('fingerprint', sa.String(length=64), nullable=False),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_failure_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_failure', sa.String(length=40), nullable=True),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint('provider'),
    )


def downgrade() -> None:
    op.drop_table('mail_transport_health')
