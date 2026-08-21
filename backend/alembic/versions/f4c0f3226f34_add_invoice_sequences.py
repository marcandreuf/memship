"""Add invoice_sequences — a gapless receipt number per year

Revision ID: f4c0f3226f34
Revises: d1a2b3c4e5f6
Create Date: 2026-08-21

The receipt number used to be COUNT(receipts in that year, is_active) + 1.
Deactivating a receipt therefore shifted the number of every receipt issued
after it, and the collision loop guarding the result skipped numbers — so an
invoice series that Spanish practice expects to be sequential and unbroken was
neither.

This replaces it with a counter per year. The backfill matters as much as the
table: without it, an existing install would restart its series at 1 and collide
with every number it has already issued. Each year starts from the highest
number actually present in that year's receipts, so numbering continues where it
left off.
"""

from alembic import op
import sqlalchemy as sa

revision = "f4c0f3226f34"
down_revision = "d1a2b3c4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoice_sequences",
        # autoincrement=False: the year is the calendar year, not a surrogate
        # key. Without it an integer primary key gets a sequence default, so a
        # row inserted without a year would be filed under year 1.
        sa.Column("year", sa.Integer(), nullable=False, autoincrement=False),
        sa.Column("next_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("year"),
    )

    # Seed each year from the highest number already issued in it.
    #
    # Read from the receipt_number rather than counting rows: the count is the
    # very thing that was wrong, and it excludes deactivated receipts whose
    # numbers are still spent. Numbers are `{prefix}-{year}-{NNNN}`, so the last
    # dash-separated field is the sequence; the regex filter keeps any
    # hand-edited number that does not end in digits out of the MAX.
    #
    # Grouped by the year in the number, not by emission_date, because that is
    # the year the number was drawn against — a receipt backdated across a year
    # boundary must not raise the wrong year's counter.
    op.execute(
        """
        INSERT INTO invoice_sequences (year, next_number)
        SELECT
            CAST(split_part(receipt_number, '-', 2) AS INTEGER) AS series_year,
            MAX(CAST(split_part(receipt_number, '-', -1) AS INTEGER)) + 1
        FROM receipts
        WHERE receipt_number ~ '^.*-[0-9]{4}-[0-9]+$'
        GROUP BY 1
        """
    )


def downgrade() -> None:
    op.drop_table("invoice_sequences")
