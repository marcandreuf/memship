"""add_user_verification_token_and_nullable_password

Revision ID: b1c2d3e4f5a6
Revises: a2b3c4d5e6f7
Create Date: 2026-07-19 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('verification_token', sa.String(length=255), nullable=True))
    op.add_column(
        'users',
        sa.Column('verification_token_expires_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        'idx_users_verification_token',
        'users',
        ['verification_token'],
        unique=False,
        postgresql_where=sa.text('verification_token IS NOT NULL'),
    )
    # SSO-only users (Google/Apple) have no password; the password login path
    # rejects a NULL hash.
    op.alter_column('users', 'password_hash', existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    # Rows with a NULL hash cannot satisfy the restored NOT NULL constraint.
    # They are SSO-only accounts, which the pre-migration schema cannot express.
    op.execute("DELETE FROM users WHERE password_hash IS NULL")
    op.alter_column('users', 'password_hash', existing_type=sa.String(length=255), nullable=False)
    op.drop_index('idx_users_verification_token', table_name='users')
    op.drop_column('users', 'verification_token_expires_at')
    op.drop_column('users', 'verification_token')