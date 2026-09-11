"""Store discount codes in upper case

Revision ID: d0e1f2a3b4c5
Revises: b8c9d0e1f2a3
Create Date: 2026-09-12

Codes were matched with a case-sensitive equality, so SUMMER20 failed against
a row holding summer20. Input is now normalised to upper case before it is
stored or looked up; this brings the existing rows in line. A row whose
upper-cased code would collide with another code on the same activity is left
as it is rather than failing the upgrade — the unique constraint stands, and
that pair is for a person to sort out.
"""

from alembic import op

revision = "d0e1f2a3b4c5"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE discount_codes d
        SET code = upper(code)
        WHERE code <> upper(code)
          AND NOT EXISTS (
              SELECT 1 FROM discount_codes o
              WHERE o.activity_id = d.activity_id
                AND o.id <> d.id
                AND o.code = upper(d.code)
          )
        """
    )


def downgrade() -> None:
    pass
