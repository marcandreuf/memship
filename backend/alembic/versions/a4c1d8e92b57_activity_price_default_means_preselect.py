"""An activity price's default means preselect it; the optional flag is removed

Revision ID: a4c1d8e92b57
Revises: e1f7a4c3b982
Create Date: 2026-11-24

``activity_prices.is_default`` and ``is_optional`` were both written by the form,
stored, and shown as a Yes/No column, and read by nothing (#601). Someone
setting up an activity asked what the two labels meant and pointed out that an
amount of 0 already displays as *Gratis*, so "default, amount 0" and "optional"
looked like the same thing. They were right, and the reason is that neither flag
did anything.

From here ``is_default`` means **preselect this price on the registration
page**, and at most one price per activity may carry it. ``is_optional`` is
removed: a registration holds a single ``price_id``, so an optional extra such
as transport or a meal alongside a main price is not representable at all, and
giving the flag a meaning would mean a line-item model for registrations that
nothing else asks for.

The de-duplication matters and is not a formality. Nothing stopped two prices on
one activity from being default, because nothing read the flag, so existing
databases can hold several. ``CREATE UNIQUE INDEX`` would simply fail on them.
The one kept per activity is the one the admin screens list first, by
``display_order`` then ``id``, so the preselected price is the one at the top of
the list the admin has been looking at rather than an arbitrary row.

The downgrade restores ``is_optional`` as ``false`` everywhere. The original
per-row values are not recoverable, which costs nothing: no code ever read them,
so no behaviour depended on which rows had it set.
"""

from alembic import op
import sqlalchemy as sa

revision = "a4c1d8e92b57"
down_revision = "e1f7a4c3b982"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep one default per activity before the index refuses the rest.
    op.execute(
        """
        UPDATE activity_prices SET is_default = false
        WHERE is_default AND id NOT IN (
            SELECT DISTINCT ON (activity_id) id
            FROM activity_prices
            WHERE is_default
            ORDER BY activity_id, display_order NULLS LAST, id
        )
        """
    )
    op.create_index(
        "uq_activity_prices_is_default",
        "activity_prices",
        ["activity_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )
    op.drop_column("activity_prices", "is_optional")


def downgrade() -> None:
    op.add_column(
        "activity_prices",
        sa.Column(
            "is_optional",
            sa.Boolean(),
            nullable=True,
            server_default=sa.false(),
        ),
    )
    op.drop_index("uq_activity_prices_is_default", table_name="activity_prices")
