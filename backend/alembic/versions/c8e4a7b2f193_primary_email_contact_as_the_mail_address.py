"""The primary email contact becomes the mailing address, with party.email as its cache

Revision ID: c8e4a7b2f193
Revises: b7d3e9a1c4f6
Create Date: 2026-11-27

``#473`` asks for the address the club mails to be separable from the address a
member signs in with. The slot for it already existed: ``contacts`` has an
``email`` channel and a partial unique index allowing one primary contact per
channel per party. Nothing read it, and no contact *type* meant "the address the
organisation writes to" — the seeded email types are ``email_work`` and
``email_other``, both explicitly secondary. So this adds ``email_main``.

The mailing address is read in six places, three of them Celery tasks and one
the opt-out lookup in ``core.email``, all of them through ``party.email``.
Repointing all six in the same change as the schema move would be a much larger
and riskier step than the issue implies, so instead **``party.email`` becomes a
cache maintained by a trigger** and every reader keeps working untouched. The
precedent is ``trg_party_display_name`` in the same table family, which keeps
``party.display_name`` following a person's name whoever writes it.

Three parts:

1. ``email_main``, the contact type that was missing.
2. A backfill, so no party silently loses its address. Every party with an
   address and no primary email contact gets one holding that address, which
   makes the trigger's view and the column agree before the trigger exists.
3. The trigger, which keeps ``party.email`` equal to the party's primary email
   contact on every insert, update and delete of one.

The downgrade drops the trigger and the type but leaves the contact rows and
``party.email`` exactly as they are: the column is still populated and still
correct at that moment, so nothing is lost by stopping the sync.
"""

import sqlalchemy as sa
from alembic import op

revision = "c8e4a7b2f193"
down_revision = "b7d3e9a1c4f6"
branch_labels = None
depends_on = None


SYNC_FUNCTION = """
CREATE OR REPLACE FUNCTION party_sync_email_from_primary_contact() RETURNS trigger AS $party_email$
DECLARE
    target_party BIGINT;
BEGIN
    -- Only an email contact can move the address. Without this every phone
    -- number written anywhere in the product would issue an extra UPDATE on
    -- party. Checked in the body rather than in a WHEN clause because this one
    -- trigger covers INSERT, UPDATE and DELETE, and WHEN cannot reference NEW
    -- on a delete or OLD on an insert.
    IF (TG_OP = 'INSERT' AND NEW.channel IS DISTINCT FROM 'email')
        OR (TG_OP = 'DELETE' AND OLD.channel IS DISTINCT FROM 'email')
        OR (TG_OP = 'UPDATE'
            AND NEW.channel IS DISTINCT FROM 'email'
            AND OLD.channel IS DISTINCT FROM 'email')
    THEN
        RETURN NULL;
    END IF;

    target_party := COALESCE(NEW.party_id, OLD.party_id);

    -- Recomputed from the table rather than taken from the row that fired:
    -- demoting an incumbent primary and promoting a new one are two statements,
    -- and reading the current winner each time means the order they arrive in
    -- cannot leave the cache holding the loser.
    UPDATE party
    SET email = (
            SELECT c.value
            FROM contacts c
            WHERE c.party_id = target_party
              AND c.channel = 'email'
              AND c.is_primary
            LIMIT 1
        ),
        updated_at = now()
    WHERE id = target_party;

    RETURN NULL;
END;
$party_email$ LANGUAGE plpgsql;
"""

CREATE_TRIGGER = """
CREATE TRIGGER trg_party_email_from_contact
    AFTER INSERT OR UPDATE OR DELETE ON contacts
    FOR EACH ROW EXECUTE FUNCTION party_sync_email_from_primary_contact();
"""


def upgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            INSERT INTO contact_types (code, name, description, channel, is_active, display_order)
            VALUES ('email_main', 'Main Email',
                    'The address the organisation writes to', 'email', true, 0)
            ON CONFLICT (code) DO NOTHING
            """
        )
    )

    # Backfill before the trigger exists. The other order would have the first
    # contact write on a party quietly overwrite an address the column already
    # held, because the trigger recomputes from a table that has no row yet.
    backfilled = bind.execute(
        sa.text(
            """
            INSERT INTO contacts
                (party_id, contact_type_id, channel, value, is_primary, display_order, is_active)
            SELECT p.id, ct.id, 'email', btrim(p.email), true, 0, true
            FROM party p
            CROSS JOIN (SELECT id FROM contact_types WHERE code = 'email_main') ct
            WHERE p.email IS NOT NULL
              AND btrim(p.email) <> ''
              AND NOT EXISTS (
                  SELECT 1 FROM contacts c
                  WHERE c.party_id = p.id
                    AND c.channel = 'email'
                    AND c.is_primary
              )
            """
        )
    ).rowcount
    print(f"  Primary email contacts backfilled: {backfilled}")

    bind.execute(sa.text(SYNC_FUNCTION))
    bind.execute(sa.text(CREATE_TRIGGER))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP TRIGGER IF EXISTS trg_party_email_from_contact ON contacts"))
    bind.execute(sa.text("DROP FUNCTION IF EXISTS party_sync_email_from_primary_contact()"))
    # The contact rows and party.email both stay. The column is populated and
    # correct at this instant, so stopping the sync loses nothing; deleting the
    # contacts would throw away addresses entered after the upgrade.
    bind.execute(
        sa.text("DELETE FROM contact_types WHERE code = 'email_main' AND NOT EXISTS ("
                "SELECT 1 FROM contacts c JOIN contact_types t ON t.id = c.contact_type_id "
                "WHERE t.code = 'email_main')")
    )
