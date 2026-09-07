"""add_credit_notes

Adds the rectifying document (credit note / *factura rectificativa*) to the
receipts table, so an issued receipt can be corrected instead of only cancelled.

An issued invoice is not amended under Spanish rules; it is rectified by a
further document carrying its own number. Both kinds therefore live in
``receipts`` and draw from the same series, and two columns are the whole of the
new stored state:

* ``document_type`` — ``invoice`` (every existing row) or ``credit_note``.
* ``rectifies_receipt_id`` — the document being rectified, ``RESTRICT`` because
  losing it would leave a negative amount pointing at nothing.

The two non-negative amount CHECKs are replaced by sign-by-document-type ones: a
credit note is stored negative, so the receipts of a member sum to what is
actually owed without a caller having to know which kind of row it is holding.

Existing rows are all invoices with a positive amount, so the new constraints
hold over them unchanged and this migration alters no behaviour on its own.

Revision ID: c9d0e1f2a3b4
Revises: e7f8a9b0c1d2
Create Date: 2026-09-07 22:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'receipts',
        sa.Column(
            'document_type',
            sa.String(length=20),
            nullable=False,
            server_default='invoice',
        ),
    )
    op.add_column(
        'receipts', sa.Column('rectifies_receipt_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_receipts_rectifies_receipt_id',
        'receipts',
        'receipts',
        ['rectifies_receipt_id'],
        ['id'],
        ondelete='RESTRICT',
    )
    op.create_index(
        'ix_receipts_rectifies_receipt_id', 'receipts', ['rectifies_receipt_id']
    )

    op.create_check_constraint(
        'valid_receipt_document_type',
        'receipts',
        "document_type IN ('invoice', 'credit_note')",
    )
    op.create_check_constraint(
        'credit_note_rectifies_a_receipt',
        'receipts',
        "(document_type = 'invoice' AND rectifies_receipt_id IS NULL)"
        " OR (document_type = 'credit_note' AND rectifies_receipt_id IS NOT NULL)",
    )

    # A CHECK constraint cannot be widened in place — drop and recreate.
    op.drop_constraint('receipt_base_non_negative', 'receipts', type_='check')
    op.create_check_constraint(
        'receipt_base_sign_matches_document_type',
        'receipts',
        "(document_type = 'invoice' AND base_amount >= 0)"
        " OR (document_type = 'credit_note' AND base_amount <= 0)",
    )
    op.drop_constraint('receipt_total_non_negative', 'receipts', type_='check')
    op.create_check_constraint(
        'receipt_total_sign_matches_document_type',
        'receipts',
        "(document_type = 'invoice' AND total_amount >= 0)"
        " OR (document_type = 'credit_note' AND total_amount <= 0)",
    )


def downgrade() -> None:
    # Credit notes are negative rows the narrowed constraints can no longer
    # describe, and they are rectifying documents in a legal series — so this
    # downgrade destroys accounting records. It is the same trade the booking
    # migration makes for booking receipts: a schema that cannot hold the rows
    # cannot keep them.
    op.execute("DELETE FROM receipts WHERE document_type = 'credit_note'")

    op.drop_constraint(
        'receipt_total_sign_matches_document_type', 'receipts', type_='check'
    )
    op.create_check_constraint(
        'receipt_total_non_negative', 'receipts', 'total_amount >= 0'
    )
    op.drop_constraint(
        'receipt_base_sign_matches_document_type', 'receipts', type_='check'
    )
    op.create_check_constraint(
        'receipt_base_non_negative', 'receipts', 'base_amount >= 0'
    )

    op.drop_constraint('credit_note_rectifies_a_receipt', 'receipts', type_='check')
    op.drop_constraint('valid_receipt_document_type', 'receipts', type_='check')

    op.drop_index('ix_receipts_rectifies_receipt_id', table_name='receipts')
    op.drop_constraint(
        'fk_receipts_rectifies_receipt_id', 'receipts', type_='foreignkey'
    )
    op.drop_column('receipts', 'rectifies_receipt_id')
    op.drop_column('receipts', 'document_type')
