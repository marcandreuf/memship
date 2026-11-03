"""Let an activity price apply to only some membership types

Revision ID: 5420c00e66da
Revises: 7b3c9e2a4d51
Create Date: 2026-11-03

Membership type was wired to activity *access* and to price nowhere, so every
eligible member saw the same prices and a "member rate / general rate" pair of
rows enforced nothing: the only check at registration was that the price
belonged to the activity (#427).

**No backfill, by design.** `NULL` and an empty array both mean "every
membership type", so every price that exists keeps applying to everyone and no
instance changes behaviour on upgrade. Any other default would need a data
migration and would silently narrow prices somebody is already selling.

An array rather than a join table, mirroring `activities.allowed_membership_types`
which solves the same problem for access: a short list, read on every price
render. It inherits that column's trade — no referential integrity, so a
deleted membership type leaves a stale id, which reads as "no member matches"
rather than as an error.

The downgrade drops the column, which discards the per-type restrictions.
Prices revert to applying to every type, which is this column's own "absent"
meaning, so a downgraded instance is permissive rather than broken.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5420c00e66da'
down_revision: Union[str, None] = '7b3c9e2a4d51'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "activity_prices",
        sa.Column("membership_type_ids", postgresql.ARRAY(sa.Integer()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("activity_prices", "membership_type_ids")
