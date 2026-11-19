"""An activity's NULL tax rate inherits the club's; 0 means exempt

Revision ID: c4f8a1d27e90
Revises: b7e4c2a9d013
Create Date: 2026-11-20

Until now ``activities.tax_rate = 0`` meant "use the club's default rate", so an
activity could not be VAT-exempt (#605). From here on NULL inherits and 0 is
exempt. Every existing 0 was written with the old meaning, so it becomes NULL:
each activity keeps billing exactly the rate it billed before.

The downgrade folds NULL back into 0, which the old code reads as "inherit". An
activity made exempt after the upgrade is indistinguishable from one that
inherits once downgraded, which is the limitation this revision removes.
"""

from alembic import op

revision = "c4f8a1d27e90"
down_revision = "b7e4c2a9d013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE activities SET tax_rate = NULL WHERE tax_rate = 0")


def downgrade() -> None:
    op.execute("UPDATE activities SET tax_rate = 0 WHERE tax_rate IS NULL")
