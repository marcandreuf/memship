"""Store the gross base on discounted receipts

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-09-12

create_receipt used to subtract the discount and store the net figure in
base_amount, with discount_amount holding the money taken off. update_receipt
then recomputed VAT from that net base and ignored the discount fields, so
editing a discounted receipt broke its arithmetic.

Receipts now keep what the admin entered — base_amount gross, discount_amount
as a percentage or a fixed sum per discount_type — and derive the rest. This
moves existing discounted rows to that shape: the discount goes back onto the
base, and a percentage discount is expressed as the percentage again. VAT and
totals are unchanged, since they were computed from the net figure either way.
"""

from alembic import op

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Right-hand sides see the old values, so the percentage is derived from
    # the gross base the row is about to hold.
    op.execute(
        """
        UPDATE receipts
        SET base_amount = base_amount + discount_amount,
            discount_amount = CASE
                WHEN discount_type = 'percentage'
                    THEN round(discount_amount * 100 / (base_amount + discount_amount), 2)
                ELSE discount_amount
            END
        WHERE discount_amount > 0
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE receipts
        SET base_amount = base_amount - CASE
                WHEN discount_type = 'percentage'
                    THEN round(base_amount * discount_amount / 100, 2)
                ELSE discount_amount
            END,
            discount_amount = CASE
                WHEN discount_type = 'percentage'
                    THEN round(base_amount * discount_amount / 100, 2)
                ELSE discount_amount
            END
        WHERE discount_amount > 0
        """
    )
