"""Add bank fields to persons.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa


revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("persons", sa.Column("bank_iban", sa.String(34), nullable=True))
    op.add_column("persons", sa.Column("bank_bic", sa.String(11), nullable=True))


def downgrade() -> None:
    op.drop_column("persons", "bank_bic")
    op.drop_column("persons", "bank_iban")
