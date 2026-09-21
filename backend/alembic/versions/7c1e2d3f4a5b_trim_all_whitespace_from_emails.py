"""Trim every whitespace character from stored email addresses, not just spaces

Revision ID: 7c1e2d3f4a5b
Revises: 20f5b7a3c3f3
Create Date: 2026-09-21

`f5a6b7c8d9e0` folded existing addresses with `lower(btrim(email))`. Postgres
`btrim` with one argument strips spaces and nothing else, where the
application's `str.strip()` strips every whitespace character. A row stored
with a tab or newline around the address before the application normalised was
therefore lower-cased by that migration and left padded, and no login can equal
it: the form strips what the member types, the row keeps its tab, and the
member is locked out of sign-in and password reset with no way back — the #191
shape again, on a narrower input (#265).

This pass trims the full set. It is a separate migration rather than a change
to `f5a6b7c8d9e0` because that one has already run on every upgraded install,
and a migration that has run is a historical record.

Like its predecessor it refuses rather than guesses: a padded row and a clean
one that become equal once trimmed are two logins, and picking a winner is not
a migration's call. The unique index keeps its narrower expression on purpose —
the application never writes a padded value, so the index only ever sees
trimmed input, and rebuilding it would cost every install an index rebuild for
rows this migration has already removed.

Self-hosters can see what the guard will find before upgrading:

    SELECT lower(btrim(email, E' \\t\\r\\n\\f\\v')) AS normalised,
           count(*), array_agg(id)
    FROM users
    GROUP BY 1
    HAVING count(*) > 1;

An empty result means the upgrade has nothing to stop for.
"""

import sqlalchemy as sa
from alembic import op

revision = "7c1e2d3f4a5b"
down_revision = "20f5b7a3c3f3"
branch_labels = None
depends_on = None

# Every character `str.strip()` removes that an address can plausibly carry.
WHITESPACE = "E' \\t\\r\\n\\f\\v'"
TRIMMED = f"lower(btrim(email, {WHITESPACE}))"

FIND_DUPLICATES = sa.text(
    f"""
    SELECT {TRIMMED} AS normalised,
           string_agg(id || ' <' || replace(replace(email, chr(9), '\\t'),
                                             chr(10), '\\n') || '>',
                      ', ' ORDER BY id) AS accounts
    FROM users
    GROUP BY {TRIMMED}
    HAVING count(*) > 1
    ORDER BY 1
    """
)

TABLES = ["users", "persons", "user_identities", "organization_settings"]


def preflight_check(conn) -> str | None:
    """Why this migration would refuse, or ``None`` if it would not.

    Discovered by name from `app/cli/preflight.py`, which runs it against the
    live database before the stack is replaced (#194).
    """
    duplicates = conn.execute(FIND_DUPLICATES).all()
    if not duplicates:
        return None
    groups = "\n".join(f"  {row.normalised}: {row.accounts}" for row in duplicates)
    return (
        f"Cannot trim email addresses: {len(duplicates)} address(es) are held by "
        "more than one account once surrounding tabs or line breaks are "
        f"removed.\n\n{groups}\n\n"
        "Decide which account keeps each address and remove or change the "
        "others, then run the upgrade again."
    )


def upgrade() -> None:
    blocked = preflight_check(op.get_bind())
    if blocked:
        raise RuntimeError(
            f"\n\n{blocked}\n"
            "Nothing has been changed — this migration made no writes.\n"
        )

    for table in TABLES:
        op.execute(
            f"UPDATE {table} SET email = {TRIMMED} "
            f"WHERE email IS NOT NULL AND email <> {TRIMMED}"
        )


def downgrade() -> None:
    # The padding was overwritten, not moved, and the application strips on
    # write regardless; there is nothing to restore.
    pass
