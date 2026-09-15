"""Store email addresses stripped and in lower case

Revision ID: f5a6b7c8d9e0
Revises: e2f3a4b5c6d7
Create Date: 2026-09-15

Addresses were compared with a case-sensitive equality everywhere they are
used, so one capital resolved to no account at all: a member who signed up as
`Marc@example.com` could not sign in as `marc@example.com`, and — because the
password-reset lookup ran the same comparison — could not recover the account
either. There was no way back without an admin editing the row (#191). Input is
now normalised at the schema boundary and in `OAuthProfile`; this brings the
existing rows in line and puts a unique index behind the invariant so the
database no longer takes the application's word for it.

Four columns are normalised: `users.email` (the login identity),
`persons.email` (the address every outgoing mail is sent to),
`user_identities.email` and `organization_settings.email`. Deliberately left
alone is `receipt_reminders.to_email` — that is a record of what was actually
sent, and rewriting it would falsify a delivery log.

Unlike the discount-code upper-casing in `d0e1f2a3b4c5`, this **aborts** rather
than skipping the rows it cannot fold. A discount code left in the old case
simply never matches and the club sees that; two accounts that differ only by
case are two people's logins, and picking a winner is not a migration's call.
The abort also gives a report a person can act on, which the raw unique
violation would not.

Self-hosters can see what the guard will find before running the upgrade:

    SELECT lower(btrim(email)) AS normalised, count(*), array_agg(id)
    FROM users
    GROUP BY lower(btrim(email))
    HAVING count(*) > 1;

An empty result means the upgrade has nothing to stop for.
"""

import sqlalchemy as sa
from alembic import op

revision = "f5a6b7c8d9e0"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None

# One expression, used by the guard, the updates and the index alike. `btrim`
# is in it as well as `lower` because a row differing only by surrounding
# whitespace collides on the update just as a differing case does, and a guard
# that checked the narrower expression would hand that collision to the index
# as an unexplained constraint violation.
NORMALISED = "lower(btrim(email))"

# EXISTS rather than a join to members: `members.user_id` carries no unique
# constraint (#187), so a join would multiply a user holding two member rows
# and trip `count(*) > 1` on a single account.
FIND_DUPLICATES = sa.text(
    f"""
    SELECT {NORMALISED} AS normalised,
           string_agg(
               id || ' <' || email || '>'
               || CASE
                    WHEN is_active IS TRUE THEN ''
                    WHEN is_active IS FALSE THEN ' [inactive]'
                    -- The column is nullable with only a Python-side default,
                    -- so a row written outside the ORM can hold NULL. Reporting
                    -- that as inactive would invite deleting the wrong account.
                    ELSE ' [is_active not set]'
                  END
               || CASE
                    WHEN last_login_at IS NULL THEN ' [never signed in]'
                    ELSE ' [last signed in ' || last_login_at::date || ']'
                  END
               || CASE
                    WHEN EXISTS (SELECT 1 FROM members m WHERE m.user_id = users.id)
                    THEN ' [has a member record]' ELSE ''
                  END,
               chr(10) || '    ' ORDER BY id
           ) AS accounts
    FROM users
    GROUP BY {NORMALISED}
    HAVING count(*) > 1
    ORDER BY 1
    """
)

TABLES = ["users", "persons", "user_identities", "organization_settings"]


def upgrade() -> None:
    duplicates = op.get_bind().execute(FIND_DUPLICATES).all()
    if duplicates:
        groups = "\n\n".join(
            f"  {row.normalised}\n    {row.accounts}" for row in duplicates
        )
        raise RuntimeError(
            f"\n\nCannot normalise email addresses: {len(duplicates)} address(es) "
            "are held by more than one account, differing only by case or "
            "surrounding whitespace.\n\n"
            f"{groups}\n\n"
            "Decide which account keeps each address and remove or change the "
            "others, then run the upgrade again.\n"
            "Nothing has been changed — this migration made no writes.\n"
        )

    for table in TABLES:
        op.execute(
            f"UPDATE {table} SET email = {NORMALISED} "
            f"WHERE email IS NOT NULL AND email <> {NORMALISED}"
        )

    op.create_index(
        "uq_users_email_lower",
        "users",
        [sa.text(NORMALISED)],
        unique=True,
    )


def downgrade() -> None:
    # Dropping the index is the reversible half. The original spelling of each
    # address is not recoverable — it was overwritten, not moved — and the
    # application normalises on write regardless, so restoring the column would
    # only last until the next save.
    op.drop_index("uq_users_email_lower", table_name="users")
