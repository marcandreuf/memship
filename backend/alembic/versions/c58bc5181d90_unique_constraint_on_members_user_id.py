"""Add a unique constraint on members.user_id

Revision ID: c58bc5181d90
Revises: f5a6b7c8d9e0
Create Date: 2026-09-15

``members.user_id`` was indexed but not unique, so a user who cancelled and
later rejoined on a fresh row — rather than reviving the old one — could hold
two member rows. Every lookup of "the caller's own member record" was then an
unordered ``.first()`` over a set the schema permitted to hold more than one:
a live and a cancelled membership could each be returned, at random, for the
same user (#187).

``current_member_or_403`` (`app/core/db_utils.py`) already orders by
``is_active DESC, id DESC`` to make the live, most recent row win. This
migration applies that same rule once, at the data level, so the constraint
below has something true to enforce: for each duplicated ``user_id``, every
row but the one that ordering would pick has its ``user_id`` cleared.

Unlike the email case in `f5a6b7c8d9e0`, this does not need a person to
decide anything and does not abort. Two member rows sharing one ``user_id``
are not two different people's accounts the way two case-variant emails can
be — they are the same account's membership history, and the rule for which
one stays reachable through it is the rule already shipped and already
governing what the app shows. Clearing ``user_id`` on the rest is exactly
what already happens when a user is deleted (``ondelete="SET NULL"``); the
member row, its number and its history are untouched, only the link from a
row nobody should be resolving through any more.

Self-hosters can see what the upgrade will find before running it:

    SELECT user_id, count(*), array_agg(id ORDER BY is_active DESC, id DESC)
    FROM members
    WHERE user_id IS NOT NULL
    GROUP BY user_id
    HAVING count(*) > 1;

An empty result means the upgrade has nothing to detach.
"""

import sqlalchemy as sa
from alembic import op

revision = "c58bc5181d90"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None

OLD_INDEX = "idx_members_user_id"
NEW_INDEX = "uq_members_user_id"

FIND_DUPLICATES = sa.text(
    """
    SELECT user_id,
           array_agg(id ORDER BY is_active DESC, id DESC) AS member_ids,
           array_agg(member_number ORDER BY is_active DESC, id DESC) AS member_numbers
    FROM members
    WHERE user_id IS NOT NULL
    GROUP BY user_id
    HAVING count(*) > 1
    ORDER BY user_id
    """
)

# The window function applies the identical ordering ``current_member_or_403``
# already uses at runtime, so which row keeps the link matches what the app
# has been resolving to since that fix landed.
DETACH_LOSING_ROWS = sa.text(
    """
    WITH ranked AS (
        SELECT id,
               row_number() OVER (
                   PARTITION BY user_id ORDER BY is_active DESC, id DESC
               ) AS rn
        FROM members
        WHERE user_id IS NOT NULL
    )
    UPDATE members
    SET user_id = NULL
    FROM ranked
    WHERE members.id = ranked.id AND ranked.rn > 1
    """
)


def upgrade() -> None:
    bind = op.get_bind()
    duplicates = bind.execute(FIND_DUPLICATES).all()
    for row in duplicates:
        kept, *detached = row.member_ids
        kept_number, *detached_numbers = row.member_numbers
        print(
            f"[members.user_id migration] user {row.user_id}: kept member "
            f"{kept} ({kept_number or 'no number'}), detached "
            f"{list(zip(detached, detached_numbers))}"
        )

    bind.execute(DETACH_LOSING_ROWS)

    op.drop_index(OLD_INDEX, table_name="members")
    op.create_index(
        NEW_INDEX,
        "members",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )


def downgrade() -> None:
    # Dropping the unique index is the reversible half. Which rows were
    # detached, and from which user, is not recoverable — the values were
    # cleared, not moved — and the application enforces the same winner
    # deterministically regardless, so restoring the old value would only
    # last until the next write.
    op.drop_index(NEW_INDEX, table_name="members")
    op.create_index(
        OLD_INDEX,
        "members",
        ["user_id"],
        unique=False,
        postgresql_where="user_id IS NOT NULL",
    )
