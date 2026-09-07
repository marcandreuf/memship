"""add_booking_pricing_and_receipts

Makes a space chargeable. ``spaces.price`` is the default a booking costs and
``space_slots.price`` overrides it for one slot, so a club sets one number for
"the court costs 10 EUR" and only reaches for the override when prime time costs
more. Both are nullable and every existing row stays NULL, which reads as free —
so this migration changes no behaviour until an admin types a price.

The receipt side needs three things. ``'booking'`` joins the allowed values of
``concepts.concept_type`` and ``receipts.origin``: the unused ``'service'`` value
would have saved a migration and cost every future report a footnote explaining
that ``'service'`` secretly means a booking, so it is left alone.

``receipts.booking_id`` is ``ON DELETE SET NULL``, unlike ``registration_id``,
which carries no rule at all. That is safe for registrations because nothing
hard-deletes one; bookings are the opposite — ``bookings.space_slot_id`` cascades
and ``delete_slot(force=True)`` deletes slot rows outright, so an admin tidying a
calendar would hit a foreign key violation the moment an affected booking had a
receipt. The receipt outlives the booking and keeps its description, which is
what the member was actually invoiced for.

Revision ID: c6d7e8f9a0b1
Revises: b6c7d8e9f0a1
Create Date: 2026-09-07 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c6d7e8f9a0b1'
down_revision: Union[str, None] = 'b6c7d8e9f0a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_TYPES = "('membership', 'activity', 'manual', 'service')"
NEW_TYPES = "('membership', 'activity', 'booking', 'manual', 'service')"


def upgrade() -> None:
    op.add_column('spaces', sa.Column('price', sa.Numeric(10, 2), nullable=True))
    op.create_check_constraint(
        'space_price_non_negative', 'spaces', 'price IS NULL OR price >= 0'
    )
    op.add_column(
        'space_slots', sa.Column('price', sa.Numeric(10, 2), nullable=True)
    )
    op.create_check_constraint(
        'space_slot_price_non_negative',
        'space_slots',
        'price IS NULL OR price >= 0',
    )

    # A CHECK constraint cannot be widened in place — drop and recreate.
    op.drop_constraint('valid_concept_type', 'concepts', type_='check')
    op.create_check_constraint(
        'valid_concept_type', 'concepts', f'concept_type IN {NEW_TYPES}'
    )
    op.drop_constraint('valid_receipt_origin', 'receipts', type_='check')
    op.create_check_constraint(
        'valid_receipt_origin', 'receipts', f'origin IN {NEW_TYPES}'
    )

    op.add_column('receipts', sa.Column('booking_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_receipts_booking_id',
        'receipts',
        'bookings',
        ['booking_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index('ix_receipts_booking_id', 'receipts', ['booking_id'])


def downgrade() -> None:
    op.drop_index('ix_receipts_booking_id', table_name='receipts')
    op.drop_constraint('fk_receipts_booking_id', 'receipts', type_='foreignkey')
    op.drop_column('receipts', 'booking_id')

    # Narrowing the constraints again means any receipt or concept raised for a
    # booking would violate it, so those rows go first — a downgrade past the
    # feature cannot keep records the schema can no longer describe.
    op.execute("DELETE FROM receipts WHERE origin = 'booking'")
    op.execute("DELETE FROM concepts WHERE concept_type = 'booking'")

    op.drop_constraint('valid_receipt_origin', 'receipts', type_='check')
    op.create_check_constraint(
        'valid_receipt_origin', 'receipts', f'origin IN {OLD_TYPES}'
    )
    op.drop_constraint('valid_concept_type', 'concepts', type_='check')
    op.create_check_constraint(
        'valid_concept_type', 'concepts', f'concept_type IN {OLD_TYPES}'
    )

    op.drop_constraint(
        'space_slot_price_non_negative', 'space_slots', type_='check'
    )
    op.drop_column('space_slots', 'price')
    op.drop_constraint('space_price_non_negative', 'spaces', type_='check')
    op.drop_column('spaces', 'price')
