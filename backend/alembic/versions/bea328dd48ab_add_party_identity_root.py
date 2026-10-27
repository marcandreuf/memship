"""Add the party identity root

Revision ID: bea328dd48ab
Revises: b7c8d9e0f1a2
Create Date: 2026-10-27

Phase 1 of ADR 0003: identity gets a single root, so the organisation can hold
a record of someone who is not a member — a donor company, a public body, a
guest. This phase is strictly additive. `party` and `party_kinds` are created,
every person is backfilled as a party of kind 'person' reusing its own id, and
`persons` becomes the first subtype (a `party_id` plus a pinned `kind`, tied by
a composite foreign key so no party can ever hold two subtypes). Nothing is
repointed: every existing query and foreign key keeps working, and the
repointing phases land separately.

`party.id` reuses `persons.id` values so the later repointing of the identity
cluster is a rename, not a remapping; the sequence is bumped past the backfill
so new parties and old persons never collide.

A person whose names are both blank would violate `party.display_name NOT
NULL`; such a row gets '(unnamed)' and is logged. The application requires
names, so this is a guard for hand-edited data, not an expected path.
"""

import sqlalchemy as sa
from alembic import op

revision = "bea328dd48ab"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


PARTY_KINDS = [
    {"code": "person", "name": "Person", "is_natural": True, "display_order": 1},
    {"code": "company", "name": "Company", "is_natural": False, "display_order": 2},
    {"code": "association", "name": "Association", "is_natural": False, "display_order": 3},
    {"code": "public_body", "name": "Public body", "is_natural": False, "display_order": 4},
    {"code": "foundation", "name": "Foundation", "is_natural": False, "display_order": 5},
    {"code": "other", "name": "Other", "is_natural": False, "display_order": 9},
]

BACKFILL_PARTIES = sa.text(
    """
    INSERT INTO party (id, kind, display_name, national_id, email, photo_url,
                       created_at, updated_at)
    SELECT id, 'person',
           coalesce(nullif(btrim(coalesce(first_name, '') || ' ' || coalesce(last_name, '')), ''),
                    '(unnamed)'),
           national_id, email, photo_url, created_at, updated_at
    FROM persons
    """
)

FIND_UNNAMED = sa.text(
    """
    SELECT id FROM persons
    WHERE btrim(coalesce(first_name, '') || ' ' || coalesce(last_name, '')) = ''
    ORDER BY id
    """
)


def upgrade() -> None:
    bind = op.get_bind()

    party_kinds = op.create_table(
        "party_kinds",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("is_natural", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.bulk_insert(party_kinds, PARTY_KINDS)

    op.create_table(
        "party",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("national_id", sa.String(50)),
        sa.Column("email", sa.String(255)),
        sa.Column("photo_url", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["kind"], ["party_kinds.code"], name="party_kind_fkey"),
        sa.UniqueConstraint("id", "kind", name="party_id_kind_key"),
    )
    op.create_index("ix_party_kind", "party", ["kind"])
    op.create_index("ix_party_display_name", "party", ["display_name"])
    op.create_index(
        "ix_party_national_id", "party", ["national_id"],
        postgresql_where=sa.text("national_id IS NOT NULL"),
    )
    op.create_index(
        "ix_party_email", "party", ["email"],
        postgresql_where=sa.text("email IS NOT NULL"),
    )

    unnamed = [row.id for row in bind.execute(FIND_UNNAMED)]
    if unnamed:
        print(f"[party migration] persons with blank names got '(unnamed)': {unnamed}")
    bind.execute(BACKFILL_PARTIES)
    bind.execute(
        sa.text(
            "SELECT setval('party_id_seq',"
            " coalesce((SELECT max(id) FROM party), 0) + 1, false)"
        )
    )

    op.add_column("persons", sa.Column("party_id", sa.BigInteger(), nullable=True))
    bind.execute(sa.text("UPDATE persons SET party_id = id"))
    op.alter_column("persons", "party_id", nullable=False)
    op.add_column(
        "persons",
        sa.Column("kind", sa.Text(), nullable=False, server_default="person"),
    )
    op.create_check_constraint("persons_kind_check", "persons", "kind = 'person'")
    op.create_unique_constraint("uq_persons_party_id", "persons", ["party_id"])
    op.create_foreign_key(
        "persons_party_fk",
        "persons",
        "party",
        ["party_id", "kind"],
        ["id", "kind"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Fully reversible: this phase is additive and nothing references party
    # yet, so dropping the subtype wiring and both tables loses only the
    # backfilled copies.
    op.drop_constraint("persons_party_fk", "persons", type_="foreignkey")
    op.drop_constraint("uq_persons_party_id", "persons", type_="unique")
    op.drop_constraint("persons_kind_check", "persons", type_="check")
    op.drop_column("persons", "kind")
    op.drop_column("persons", "party_id")
    op.drop_table("party")
    op.drop_table("party_kinds")
