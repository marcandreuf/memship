"""add_custom_profile_fields

Adds the custom profile field definition + value tables (EAV), and drops three
JSONB columns that have existed since the initial schema and were never read or
written by any code: ``persons.custom_fields``, ``members.custom_data`` and
``membership_types.custom_fields_schema``. ``persons.custom_fields`` in
particular collides by name with this feature. They are always empty, so the
drop loses nothing — but it is destructive DDL, so it is called out in the
release notes.

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-07-21 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'custom_field_definitions',
        sa.Column('id', sa.Integer(), nullable=False),
        # Stable slug used as the API key; immutable after creation.
        sa.Column('key', sa.String(length=50), nullable=False),
        sa.Column('field_type', sa.String(length=20), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=False),
        sa.Column('labels', postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column('help_text', sa.String(length=255), nullable=True),
        sa.Column('options', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('required', sa.Boolean(), nullable=False, server_default=sa.false()),
        # Super admin is always write; `restricted` follows admin_access.
        sa.Column('member_access', sa.String(length=10), nullable=False,
                  server_default='read'),
        sa.Column('admin_access', sa.String(length=10), nullable=False,
                  server_default='write'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint(
            "field_type IN ('text', 'textarea', 'number', 'date', 'boolean', 'select')",
            name='valid_custom_field_type',
        ),
        sa.CheckConstraint(
            "member_access IN ('hidden', 'read', 'write')",
            name='valid_custom_field_member_access',
        ),
        sa.CheckConstraint(
            "admin_access IN ('read', 'write')",
            name='valid_custom_field_admin_access',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    op.create_index(
        'ix_custom_field_definitions_active_order',
        'custom_field_definitions',
        ['active', 'sort_order'],
        unique=False,
    )

    op.create_table(
        'custom_field_values',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('definition_id', sa.Integer(), nullable=False),
        sa.Column('person_id', sa.Integer(), nullable=False),
        # Canonical string form; coerced per definition.field_type by the service.
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['definition_id'], ['custom_field_definitions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['person_id'], ['persons.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('definition_id', 'person_id',
                            name='uq_custom_field_value_definition_person'),
    )
    op.create_index(
        'ix_custom_field_values_person', 'custom_field_values', ['person_id'], unique=False
    )

    # Vestigial columns from the initial schema — never read or written.
    op.drop_column('persons', 'custom_fields')
    op.drop_column('members', 'custom_data')
    op.drop_column('membership_types', 'custom_fields_schema')


def downgrade() -> None:
    op.add_column(
        'membership_types',
        sa.Column('custom_fields_schema', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        'members',
        sa.Column('custom_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        'persons',
        sa.Column('custom_fields', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.drop_index('ix_custom_field_values_person', table_name='custom_field_values')
    op.drop_table('custom_field_values')
    op.drop_index(
        'ix_custom_field_definitions_active_order', table_name='custom_field_definitions'
    )
    op.drop_table('custom_field_definitions')
