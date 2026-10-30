"""Repoint the identity cluster to party

Revision ID: 29a3872dad10
Revises: bea328dd48ab
Create Date: 2026-10-27

Phase 2 of ADR 0003. A login, a membership and a custom field value stop being
facts about a person row and become facts about a party: `users`, `members`
and `custom_field_values` move from `person_id` to `party_id`, and
`members.guardian_person_id` becomes `guardian_party_id`, still pointing at the
`persons` subtype because a guardian is always a natural person.

These are remaps, not renames: `persons.id` and `persons.party_id` are equal
for every row that existed before the party backfill, but the two sequences
advance independently afterwards, so each column is remapped through `persons`
before its rename. On a database that went straight from 2.x to here the
UPDATEs are no-ops.

Two rules the schema never enforced become partial unique indexes, scoped to
active rows so that deactivated history can keep its `party_id`:

* one active login per party (`idx_users_person_id` was not unique, so a
  person could hold two logins and `person.user` returned whichever row came
  back first)
* one active membership per party (same defect, same shape)

Existing violations resolve deterministically before each index lands: the
winner is the most recently used login (`last_login_at`, then `created_at`,
then id) or the most recent member row (`is_active DESC, id DESC`, the same
ordering `current_member_or_403` already applies); every other row is
deactivated, never deleted, and logged.

`members.user_id` is dropped. It and `users.person_id` both linked login to
identity; with both ends now carrying a unique `party_id` the member for a
logged-in user is one join (`users.party_id = members.party_id`) and a third
edge that can disagree is structure the schema is better off without.

`party.display_name` stops being write-once: a trigger keeps it in step with
`persons.first_name`/`last_name`. A trigger rather than service code because
the seeder, the CLI and future migrations all write `persons` directly. A
deliberate denormalisation; `sepa_mandates.debtor_name` is the precedent.
"""

import sqlalchemy as sa
from alembic import op

revision = "29a3872dad10"
down_revision = "bea328dd48ab"
branch_labels = None
depends_on = None


FIND_DUPLICATE_ACTIVE_LOGINS = sa.text(
    """
    SELECT person_id,
           array_agg(id ORDER BY last_login_at DESC NULLS LAST,
                     created_at DESC, id DESC) AS user_ids
    FROM users
    WHERE is_active
    GROUP BY person_id
    HAVING count(*) > 1
    ORDER BY person_id
    """
)

DEACTIVATE_LOSING_LOGINS = sa.text(
    """
    WITH ranked AS (
        SELECT id,
               row_number() OVER (
                   PARTITION BY person_id
                   ORDER BY last_login_at DESC NULLS LAST, created_at DESC, id DESC
               ) AS rn
        FROM users
        WHERE is_active
    )
    UPDATE users SET is_active = false
    FROM ranked
    WHERE users.id = ranked.id AND ranked.rn > 1
    """
)

FIND_DUPLICATE_ACTIVE_MEMBERS = sa.text(
    """
    SELECT person_id,
           array_agg(id ORDER BY id DESC) AS member_ids
    FROM members
    WHERE is_active
    GROUP BY person_id
    HAVING count(*) > 1
    ORDER BY person_id
    """
)

DEACTIVATE_LOSING_MEMBERS = sa.text(
    """
    WITH ranked AS (
        SELECT id,
               row_number() OVER (PARTITION BY person_id ORDER BY id DESC) AS rn
        FROM members
        WHERE is_active
    )
    UPDATE members SET is_active = false
    FROM ranked
    WHERE members.id = ranked.id AND ranked.rn > 1
    """
)

DISPLAY_NAME_TRIGGER = """
CREATE OR REPLACE FUNCTION party_sync_display_name_from_person() RETURNS trigger AS $$
BEGIN
    UPDATE party
    SET display_name = btrim(coalesce(NEW.first_name, '') || ' ' || coalesce(NEW.last_name, '')),
        updated_at = now()
    WHERE id = NEW.party_id
      AND btrim(coalesce(NEW.first_name, '') || ' ' || coalesce(NEW.last_name, '')) <> '';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_party_display_name
    AFTER INSERT OR UPDATE OF first_name, last_name ON persons
    FOR EACH ROW EXECUTE FUNCTION party_sync_display_name_from_person();
"""


def _remap_through_persons(bind, table: str, column: str) -> None:
    bind.execute(
        sa.text(
            f"UPDATE {table} SET {column} = p.party_id "
            f"FROM persons p WHERE p.id = {table}.{column} "
            f"AND {table}.{column} IS DISTINCT FROM p.party_id"
        )
    )


def upgrade() -> None:
    bind = op.get_bind()

    # --- users ---------------------------------------------------------------
    for row in bind.execute(FIND_DUPLICATE_ACTIVE_LOGINS).all():
        kept, *deactivated = row.user_ids
        print(
            f"[party repoint] person {row.person_id}: kept login {kept}, "
            f"deactivated {deactivated}"
        )
    bind.execute(DEACTIVATE_LOSING_LOGINS)

    _remap_through_persons(bind, "users", "person_id")
    op.alter_column("users", "person_id", new_column_name="party_id", type_=sa.BigInteger())
    op.drop_constraint("users_person_id_fkey", "users", type_="foreignkey")
    op.create_foreign_key(
        "users_party_id_fkey", "users", "party", ["party_id"], ["id"], ondelete="CASCADE"
    )
    op.drop_index("idx_users_person_id", table_name="users")
    op.create_index(
        "uq_users_one_active_per_party", "users", ["party_id"],
        unique=True, postgresql_where=sa.text("is_active"),
    )
    op.create_index("idx_users_party_id", "users", ["party_id"])

    # --- members -------------------------------------------------------------
    for row in bind.execute(FIND_DUPLICATE_ACTIVE_MEMBERS).all():
        kept, *deactivated = row.member_ids
        print(
            f"[party repoint] person {row.person_id}: kept member {kept}, "
            f"deactivated {deactivated}"
        )
    bind.execute(DEACTIVATE_LOSING_MEMBERS)

    _remap_through_persons(bind, "members", "person_id")
    op.alter_column("members", "person_id", new_column_name="party_id", type_=sa.BigInteger())
    op.drop_constraint("members_person_id_fkey", "members", type_="foreignkey")
    op.create_foreign_key(
        "members_party_id_fkey", "members", "party", ["party_id"], ["id"], ondelete="CASCADE"
    )
    op.drop_index("idx_members_person_id", table_name="members")
    op.create_index(
        "uq_members_one_active_per_party", "members", ["party_id"],
        unique=True, postgresql_where=sa.text("is_active"),
    )
    op.create_index("idx_members_party_id", "members", ["party_id"])

    _remap_through_persons(bind, "members", "guardian_person_id")
    op.alter_column(
        "members", "guardian_person_id", new_column_name="guardian_party_id",
        type_=sa.BigInteger(),
    )
    op.drop_constraint("members_guardian_person_id_fkey", "members", type_="foreignkey")
    op.create_foreign_key(
        "members_guardian_party_id_fkey", "members", "persons",
        ["guardian_party_id"], ["party_id"], ondelete="SET NULL",
    )

    op.drop_index("uq_members_user_id", table_name="members")
    op.drop_column("members", "user_id")

    # --- custom_field_values -------------------------------------------------
    _remap_through_persons(bind, "custom_field_values", "person_id")
    op.alter_column(
        "custom_field_values", "person_id", new_column_name="party_id",
        type_=sa.BigInteger(),
    )
    op.drop_constraint(
        "custom_field_values_person_id_fkey", "custom_field_values", type_="foreignkey"
    )
    op.create_foreign_key(
        "custom_field_values_party_id_fkey", "custom_field_values", "party",
        ["party_id"], ["id"], ondelete="CASCADE",
    )
    bind.execute(sa.text(
        "ALTER TABLE custom_field_values "
        "RENAME CONSTRAINT uq_custom_field_value_definition_person "
        "TO uq_custom_field_value_definition_party"
    ))
    bind.execute(sa.text(
        "ALTER INDEX ix_custom_field_values_person RENAME TO ix_custom_field_values_party"
    ))

    # --- display_name maintenance --------------------------------------------
    op.execute(DISPLAY_NAME_TRIGGER)


def downgrade() -> None:
    # The renames, remaps and the trigger reverse cleanly. Which logins and
    # member rows were deactivated is logged but not recorded in data, so they
    # stay deactivated: reactivating them would recreate the ambiguity the
    # upgrade resolved.
    op.execute("DROP TRIGGER trg_party_display_name ON persons")
    op.execute("DROP FUNCTION party_sync_display_name_from_person()")

    bind = op.get_bind()

    op.drop_constraint("custom_field_values_party_id_fkey", "custom_field_values", type_="foreignkey")
    bind.execute(sa.text(
        "ALTER INDEX ix_custom_field_values_party RENAME TO ix_custom_field_values_person"
    ))
    bind.execute(sa.text(
        "ALTER TABLE custom_field_values "
        "RENAME CONSTRAINT uq_custom_field_value_definition_party "
        "TO uq_custom_field_value_definition_person"
    ))
    op.alter_column("custom_field_values", "party_id", new_column_name="person_id", type_=sa.Integer())
    bind.execute(sa.text(
        "UPDATE custom_field_values SET person_id = p.id FROM persons p "
        "WHERE p.party_id = custom_field_values.person_id"
    ))
    op.create_foreign_key(
        "custom_field_values_person_id_fkey", "custom_field_values", "persons",
        ["person_id"], ["id"], ondelete="CASCADE",
    )

    op.add_column("members", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_index(
        "uq_members_user_id", "members", ["user_id"],
        unique=True, postgresql_where=sa.text("user_id IS NOT NULL"),
    )

    op.drop_constraint("members_guardian_party_id_fkey", "members", type_="foreignkey")
    op.alter_column("members", "guardian_party_id", new_column_name="guardian_person_id", type_=sa.Integer())
    bind.execute(sa.text(
        "UPDATE members SET guardian_person_id = p.id FROM persons p "
        "WHERE p.party_id = members.guardian_person_id"
    ))
    op.create_foreign_key(
        "members_guardian_person_id_fkey", "members", "persons",
        ["guardian_person_id"], ["id"], ondelete="SET NULL",
    )

    op.drop_index("idx_members_party_id", table_name="members")
    op.drop_index("uq_members_one_active_per_party", table_name="members")
    op.drop_constraint("members_party_id_fkey", "members", type_="foreignkey")
    op.alter_column("members", "party_id", new_column_name="person_id", type_=sa.Integer())
    bind.execute(sa.text(
        "UPDATE members SET person_id = p.id FROM persons p "
        "WHERE p.party_id = members.person_id"
    ))
    op.create_foreign_key(
        "members_person_id_fkey", "members", "persons",
        ["person_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("idx_members_person_id", "members", ["person_id"])

    op.drop_index("idx_users_party_id", table_name="users")
    op.drop_index("uq_users_one_active_per_party", table_name="users")
    op.drop_constraint("users_party_id_fkey", "users", type_="foreignkey")
    op.alter_column("users", "party_id", new_column_name="person_id", type_=sa.Integer())
    bind.execute(sa.text(
        "UPDATE users SET person_id = p.id FROM persons p "
        "WHERE p.party_id = users.person_id"
    ))
    op.create_foreign_key(
        "users_person_id_fkey", "users", "persons",
        ["person_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("idx_users_person_id", "users", ["person_id"])

    # After the users block, not with the members block above: this reads
    # users.person_id, which only exists once party_id has been renamed back a
    # few lines up. Ordering it with the other members statements is a hard
    # failure on every downgrade, whatever the data holds (memship#474).
    bind.execute(sa.text(
        "UPDATE members m SET user_id = u.id FROM users u "
        "WHERE u.person_id = m.person_id AND u.is_active"
    ))
