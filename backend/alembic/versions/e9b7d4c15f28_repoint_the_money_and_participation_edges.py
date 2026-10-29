"""Repoint the money and participation edges to party.

Phase 4 of the party refactor (ADR 0003). `receipts`, `sepa_mandates`,
`registrations` and `bookings` stop pointing at a membership and point at the
identity behind it. This is the change that makes a donation from a company
or a non-member expressible (#456, #445), and it removes the schema guarantee
that only members participate (#429) — member-only activities and spaces are
a service-layer rule from here on. `announcement_recipients` stays on
`members` deliberately: it is a snapshot of the membership audience at send
time.

Unlike the identity phases these are remaps, not renames: `member.id` and
`party.id` are different values, so every column is rewritten through
`members`. The old partial uniques drop BEFORE each remap — member ids and
party ids overlap numerically, so mid-UPDATE a new value can transiently
equal another row's old value (found by running the target DDL against
seeded rows). The remap is total and deterministic: every row's member
exists (`NOT NULL` plus FK) and carries exactly one `party_id`.

The downgrade maps each row back through its party's membership, active row
first. A row whose party holds no membership at all — possible only for data
created after this migration — cannot be represented in the old schema, so
the downgrade refuses with a count rather than silently deleting money or
participation history.

Revision ID: e9b7d4c15f28
Revises: e3f8c2a91b47
Create Date: 2026-10-27
"""

import sqlalchemy as sa
from alembic import op

revision = "e9b7d4c15f28"
down_revision = "e3f8c2a91b47"
branch_labels = None
depends_on = None


def _log(message: str) -> None:
    print(f"[party migration] {message}")


# (table, old fk name, new fk name, ondelete, old index, new index)
EDGES = [
    ("receipts", "receipts_member_id_fkey", "receipts_party_id_fkey",
     None, "ix_receipts_member_id", "ix_receipts_party_id"),
    ("sepa_mandates", "sepa_mandates_member_id_fkey", "sepa_mandates_party_id_fkey",
     None, "ix_sepa_mandates_member_id", "ix_sepa_mandates_party_id"),
    ("registrations", "registrations_member_id_fkey", "registrations_party_id_fkey",
     "CASCADE", "idx_registrations_member_id", "idx_registrations_party_id"),
    ("bookings", "bookings_member_id_fkey", "bookings_party_id_fkey",
     "CASCADE", "ix_bookings_member", "ix_bookings_party"),
]

# Partial uniques that key on the repointed column: dropped before the remap,
# recreated on the new key after it.
OLD_UNIQUES = {
    "sepa_mandates": "uq_sepa_mandates_one_active_per_member",
    "registrations": "uq_registration_active_member",
    "bookings": "uq_bookings_member_slot_active",
}


def upgrade() -> None:
    bind = op.get_bind()

    for table, old_fk, new_fk, ondelete, old_ix, new_ix in EDGES:
        if table in OLD_UNIQUES:
            op.drop_index(OLD_UNIQUES[table], table_name=table)

        op.alter_column(table, "member_id", type_=sa.BigInteger())
        count = bind.execute(sa.text(
            f"UPDATE {table} t SET member_id = m.party_id "
            f"FROM members m WHERE m.id = t.member_id"
        )).rowcount
        _log(f"{table}: repointed {count} rows to party")

        op.alter_column(table, "member_id", new_column_name="party_id")
        op.drop_constraint(old_fk, table, type_="foreignkey")
        op.create_foreign_key(
            new_fk, table, "party", ["party_id"], ["id"], ondelete=ondelete
        )
        bind.execute(sa.text(f"ALTER INDEX {old_ix} RENAME TO {new_ix}"))

    op.create_index(
        "uq_sepa_mandates_one_active_per_party", "sepa_mandates", ["party_id"],
        unique=True, postgresql_where=sa.text("status = 'active' AND is_active = true"),
    )
    op.create_index(
        "uq_registration_active_party", "registrations", ["activity_id", "party_id"],
        unique=True, postgresql_where=sa.text("status != 'cancelled'"),
    )
    op.create_index(
        "uq_bookings_party_slot_active", "bookings", ["space_slot_id", "party_id"],
        unique=True, postgresql_where=sa.text("status IN ('booked', 'waitlisted')"),
    )


NEW_UNIQUES = (
    ("sepa_mandates", "uq_sepa_mandates_one_active_per_party"),
    ("registrations", "uq_registration_active_party"),
    ("bookings", "uq_bookings_party_slot_active"),
)


def downgrade() -> None:
    bind = op.get_bind()

    # Refuse rather than delete: a row whose party holds no membership has no
    # representation in the old schema, and these rows are money and history.
    for table, *_ in EDGES:
        stranded = bind.execute(sa.text(
            f"SELECT count(*) FROM {table} t "
            f"WHERE NOT EXISTS (SELECT 1 FROM members m WHERE m.party_id = t.party_id)"
        )).scalar_one()
        if stranded:
            raise RuntimeError(
                f"cannot downgrade: {stranded} {table} rows belong to parties "
                "with no membership; the pre-party schema cannot hold them"
            )

    for table, name in NEW_UNIQUES:
        op.drop_index(name, table_name=table)

    for table, old_fk, new_fk, ondelete, old_ix, new_ix in EDGES:
        # Active membership first, then the newest row: the same preference
        # the transitional API uses when it names a member for a party.
        count = bind.execute(sa.text(f"""
            UPDATE {table} t SET party_id = picked.id
            FROM (
                SELECT DISTINCT ON (party_id) party_id, id
                FROM members ORDER BY party_id, is_active DESC, id DESC
            ) picked
            WHERE picked.party_id = t.party_id
        """)).rowcount
        _log(f"{table}: mapped {count} rows back to members")

        op.drop_constraint(new_fk, table, type_="foreignkey")
        op.alter_column(table, "party_id", new_column_name="member_id")
        op.alter_column(table, "member_id", type_=sa.Integer())
        op.create_foreign_key(
            old_fk, table, "members", ["member_id"], ["id"], ondelete=ondelete
        )
        bind.execute(sa.text(f"ALTER INDEX {new_ix} RENAME TO {old_ix}"))

    op.create_index(
        "uq_sepa_mandates_one_active_per_member", "sepa_mandates", ["member_id"],
        unique=True, postgresql_where=sa.text("status = 'active' AND is_active = true"),
    )
    op.create_index(
        "uq_registration_active_member", "registrations", ["activity_id", "member_id"],
        unique=True, postgresql_where=sa.text("status != 'cancelled'"),
    )
    op.create_index(
        "uq_bookings_member_slot_active", "bookings", ["space_slot_id", "member_id"],
        unique=True, postgresql_where=sa.text("status IN ('booked', 'waitlisted')"),
    )
