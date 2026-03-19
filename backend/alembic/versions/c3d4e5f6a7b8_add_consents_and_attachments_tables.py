"""add_consents_and_attachments_tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-19 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # activity_consents
    op.create_table(
        "activity_consents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_mandatory", sa.Boolean(), nullable=True, server_default="true"),
        sa.Column("display_order", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_activity_consents_activity_id", "activity_consents", ["activity_id"])

    # activity_attachment_types
    op.create_table(
        "activity_attachment_types",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("allowed_extensions", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("max_file_size_mb", sa.Integer(), nullable=True, server_default="5"),
        sa.Column("is_mandatory", sa.Boolean(), nullable=True, server_default="true"),
        sa.Column("display_order", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_activity_attachment_types_activity_id", "activity_attachment_types", ["activity_id"])

    # registration_consents
    op.create_table(
        "registration_consents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("registration_id", sa.Integer(), nullable=False),
        sa.Column("activity_consent_id", sa.Integer(), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("accepted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["registration_id"], ["registrations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["activity_consent_id"], ["activity_consents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("registration_id", "activity_consent_id", name="uq_registration_consent"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_registration_consents_registration_id", "registration_consents", ["registration_id"])

    # registration_attachments
    op.create_table(
        "registration_attachments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("registration_id", sa.Integer(), nullable=False),
        sa.Column("attachment_type_id", sa.Integer(), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["registration_id"], ["registrations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attachment_type_id"], ["activity_attachment_types.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_registration_attachments_registration_id", "registration_attachments", ["registration_id"])


def downgrade() -> None:
    op.drop_index("idx_registration_attachments_registration_id", table_name="registration_attachments")
    op.drop_table("registration_attachments")
    op.drop_index("idx_registration_consents_registration_id", table_name="registration_consents")
    op.drop_table("registration_consents")
    op.drop_index("idx_activity_attachment_types_activity_id", table_name="activity_attachment_types")
    op.drop_table("activity_attachment_types")
    op.drop_index("idx_activity_consents_activity_id", table_name="activity_consents")
    op.drop_table("activity_consents")
