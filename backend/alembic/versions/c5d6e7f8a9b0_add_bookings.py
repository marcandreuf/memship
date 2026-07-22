"""add_bookings

Adds the Simple Bookings tables: ``spaces`` (bookable resources with daily
opening hours), ``space_slots`` (admin-defined recurring weekly slots with a
capacity), and ``bookings`` (a member holding a slot-instance, booked or
waitlisted). Capacity is enforced in the service under a row lock; the partial
unique index below only stops a member holding two active rows for the same
slot-instance.

Revision ID: c5d6e7f8a9b0
Revises: b3c4d5e6f7a8
Create Date: 2026-07-22 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c5d6e7f8a9b0'
down_revision: Union[str, None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'spaces',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('space_type', sa.String(length=50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('open_time', sa.Time(), nullable=False),
        sa.Column('close_time', sa.Time(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint('close_time > open_time', name='space_hours_valid'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_spaces_active', 'spaces', ['is_active'], unique=False)

    op.create_table(
        'space_slots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('space_id', sa.Integer(), nullable=False),
        sa.Column('weekday', sa.SmallInteger(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('capacity', sa.SmallInteger(), nullable=False, server_default='1'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint('weekday BETWEEN 0 AND 6', name='space_slot_weekday_valid'),
        sa.CheckConstraint('end_time > start_time', name='space_slot_time_valid'),
        sa.CheckConstraint('capacity >= 1', name='space_slot_capacity_valid'),
        sa.ForeignKeyConstraint(['space_id'], ['spaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_space_slots_space', 'space_slots', ['space_id'], unique=False)

    op.create_table(
        'bookings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('space_slot_id', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=False),
        sa.Column('booking_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='booked'),
        sa.Column('waitlisted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint(
            "status IN ('booked', 'waitlisted', 'cancelled')",
            name='booking_status_valid',
        ),
        sa.ForeignKeyConstraint(['space_slot_id'], ['space_slots.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cancelled_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_bookings_slot_date', 'bookings', ['space_slot_id', 'booking_date'], unique=False)
    op.create_index('ix_bookings_member', 'bookings', ['member_id'], unique=False)
    op.create_index(
        'uq_bookings_member_slot_date_active',
        'bookings',
        ['space_slot_id', 'booking_date', 'member_id'],
        unique=True,
        postgresql_where=sa.text("status IN ('booked', 'waitlisted')"),
    )


def downgrade() -> None:
    op.drop_index('uq_bookings_member_slot_date_active', table_name='bookings')
    op.drop_index('ix_bookings_member', table_name='bookings')
    op.drop_index('ix_bookings_slot_date', table_name='bookings')
    op.drop_table('bookings')
    op.drop_index('ix_space_slots_space', table_name='space_slots')
    op.drop_table('space_slots')
    op.drop_index('ix_spaces_active', table_name='spaces')
    op.drop_table('spaces')
