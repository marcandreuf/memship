"""add_registrations_table

Revision ID: a1b2c3d4e5f6
Revises: 7eb6d537f358
Create Date: 2026-03-19 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "7eb6d537f358"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "registrations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("modality_id", sa.Integer(), nullable=True),
        sa.Column("price_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="confirmed"),
        sa.Column("registration_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default="{}"),
        sa.Column("member_notes", sa.Text(), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by", sa.Integer(), nullable=True),
        sa.Column("cancelled_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["modality_id"], ["activity_modalities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["price_id"], ["activity_prices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["cancelled_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status IN ('confirmed', 'waitlist', 'cancelled', 'pending')",
            name="valid_registration_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_registration_active_member",
        "registrations",
        ["activity_id", "member_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'cancelled'"),
    )
    op.create_index("idx_registrations_activity_id", "registrations", ["activity_id"])
    op.create_index("idx_registrations_member_id", "registrations", ["member_id"])
    op.create_index("idx_registrations_status", "registrations", ["status"])


def downgrade() -> None:
    op.drop_index("uq_registration_active_member", table_name="registrations")
    op.drop_index("idx_registrations_status", table_name="registrations")
    op.drop_index("idx_registrations_member_id", table_name="registrations")
    op.drop_index("idx_registrations_activity_id", table_name="registrations")
    op.drop_table("registrations")
