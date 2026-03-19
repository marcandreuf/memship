"""add_discount_codes_table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-19 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create discount_codes table
    op.create_table(
        "discount_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("discount_type", sa.String(length=20), nullable=False),
        sa.Column("discount_value", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("current_uses", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="CASCADE"),
        sa.CheckConstraint("discount_type IN ('percentage', 'fixed')", name="valid_discount_type"),
        sa.CheckConstraint("discount_value > 0", name="discount_value_positive"),
        sa.CheckConstraint("discount_type != 'percentage' OR discount_value <= 100", name="percentage_max_100"),
        sa.UniqueConstraint("activity_id", "code", name="uq_discount_code_per_activity"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_discount_codes_activity_id", "discount_codes", ["activity_id"])
    op.create_index("idx_discount_codes_code", "discount_codes", ["code"])

    # Add discount_code_id, original_amount, discounted_amount to registrations
    op.add_column("registrations", sa.Column("discount_code_id", sa.Integer(), nullable=True))
    op.add_column("registrations", sa.Column("original_amount", sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column("registrations", sa.Column("discounted_amount", sa.Numeric(precision=10, scale=2), nullable=True))
    op.create_foreign_key(
        "fk_registrations_discount_code_id",
        "registrations",
        "discount_codes",
        ["discount_code_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_registrations_discount_code_id", "registrations", type_="foreignkey")
    op.drop_column("registrations", "discounted_amount")
    op.drop_column("registrations", "original_amount")
    op.drop_column("registrations", "discount_code_id")
    op.drop_index("idx_discount_codes_code", table_name="discount_codes")
    op.drop_index("idx_discount_codes_activity_id", table_name="discount_codes")
    op.drop_table("discount_codes")
