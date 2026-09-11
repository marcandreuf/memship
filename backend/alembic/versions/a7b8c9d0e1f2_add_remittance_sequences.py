"""Add remittance_sequences — a locked remittance number per year

Revision ID: a7b8c9d0e1f2
Revises: c9d0e1f2a3b4
Create Date: 2026-09-11

Receipt numbers moved to a per-year counter locked FOR UPDATE in
f4c0f3226f34; remittance numbers stayed on COUNT(remittances in year) + 1,
which two concurrent generations can both read before either inserts. This
gives remittances the same counter, backfilled from the highest number each
year has already issued so an existing install continues its series.
"""

from alembic import op
import sqlalchemy as sa

revision = "a7b8c9d0e1f2"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "remittance_sequences",
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

    # Seed each year from the highest number already issued in it, read from
    # the number itself rather than by counting rows. Numbers are
    # `REM-{year}-{NNNN}`; the year is taken from the number, not from
    # emission_date, because that is the series the number was drawn against.
    op.execute(
        """
        INSERT INTO remittance_sequences (year, next_number)
        SELECT
            CAST(substring(remittance_number from '([0-9]{4})-[0-9]+$') AS INTEGER)
                AS series_year,
            MAX(CAST(substring(remittance_number from '([0-9]+)$') AS INTEGER)) + 1
        FROM remittances
        WHERE remittance_number ~ '[0-9]{4}-[0-9]+$'
        GROUP BY 1
        """
    )


def downgrade() -> None:
    op.drop_table("remittance_sequences")
