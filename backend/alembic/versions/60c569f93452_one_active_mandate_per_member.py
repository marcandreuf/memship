"""One active SEPA mandate per member

Revision ID: 60c569f93452
Revises: 8d2f3e4a5b6c
Create Date: 2026-10-16

A member could hold two active mandates at once. Nothing prevented it, and the
collection picked between them with "latest by created_at" and no tie-break —
`created_at` is a server default, so two mandates written in the same
transaction share a timestamp and the winner was whichever row the query
happened to return first. Which bank account a member was debited from was not
decided by anything the product states (#394).

A member has one account the club collects from, so this makes the second one
unrepresentable rather than guarded. Existing duplicates are resolved the way
the old code tried to: the newest by `created_at`, then by `id`, stays active
and the rest are cancelled, with a note saying why — a cancelled mandate is a
normal state the screens already render, and the alternative is a migration
that cannot run.
"""

import sqlalchemy as sa
from alembic import op

revision = "60c569f93452"
down_revision = "8d2f3e4a5b6c"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_sepa_mandates_one_active_per_member"


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY member_id
                           ORDER BY created_at DESC, id DESC
                       ) AS position
                  FROM sepa_mandates
                 WHERE status = 'active' AND is_active = true
            )
            UPDATE sepa_mandates AS m
               SET status = 'cancelled',
                   cancelled_at = now(),
                   notes = COALESCE(m.notes || E'\\n', '')
                           || 'Cancelled automatically: a member may hold only '
                           || 'one active mandate, and a newer one existed.'
              FROM ranked
             WHERE m.id = ranked.id
               AND ranked.position > 1
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            CREATE UNIQUE INDEX {INDEX_NAME}
                ON sepa_mandates (member_id)
             WHERE status = 'active' AND is_active = true
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f"DROP INDEX IF EXISTS {INDEX_NAME}"))
