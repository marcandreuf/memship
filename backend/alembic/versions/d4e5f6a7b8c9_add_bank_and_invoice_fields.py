"""Add bank and invoice fields to organization_settings.

Revision ID: d4e5f6a7b8c9
Revises: f993a3100855
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organization_settings", sa.Column("bank_name", sa.String(255), nullable=True))
    op.add_column("organization_settings", sa.Column("bank_iban", sa.String(34), nullable=True))
    op.add_column("organization_settings", sa.Column("bank_bic", sa.String(11), nullable=True))
    op.add_column("organization_settings", sa.Column("invoice_prefix", sa.String(10), server_default="INV", nullable=True))
    op.add_column("organization_settings", sa.Column("invoice_next_number", sa.Integer(), server_default="1", nullable=True))


def downgrade() -> None:
    op.drop_column("organization_settings", "invoice_next_number")
    op.drop_column("organization_settings", "invoice_prefix")
    op.drop_column("organization_settings", "bank_bic")
    op.drop_column("organization_settings", "bank_iban")
    op.drop_column("organization_settings", "bank_name")
