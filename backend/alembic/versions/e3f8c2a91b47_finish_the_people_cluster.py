"""Finish the people cluster: real owners, the club as a party, the key handover.

Phase 3 of the party refactor (ADR 0003). Four moves, in dependency order:

1. **The club becomes a party.** One `association` row, and
   ``organization_settings.party_id`` points at it. The settings row keeps the
   identity columns until the surface phase; nothing reads the copies yet.
2. **Addresses and contacts get real foreign keys.** The polymorphic
   ``entity_type``/``entity_id`` pair — no FK, no cascade, orphans invisible —
   becomes an exclusive arc on ``addresses`` (``party_id``/``space_id``, exactly
   one set) and a plain NOT NULL ``party_id`` on ``contacts`` (its old CHECK
   only ever allowed ``'person'``). Orphaned rows are dropped and counted, per
   the data policy. ``address_types`` goes with them: no endpoint, no UI, dead.
3. **Channels become structural.** ``contact_channels`` registry,
   ``contact_types.channel``, and a denormalised ``contacts.channel`` tied to
   its type by a composite FK so the two cannot disagree — which is what lets
   a partial unique say "one primary per channel".
4. **The primary key hands over.** ``persons.email``/``national_id``/
   ``photo_url`` move up to ``party`` (the person's values win over any stale
   Phase 1 copy), then ``persons.id`` is dropped and ``party_id`` becomes the
   key. Nothing referenced ``persons.id`` any more; the guardian FK is rebuilt
   on the new key.

Everything data-destructive here is resolved unattended and logged: orphan
counts, demoted duplicate primaries, contact types with an unguessable
channel. The downgrade rebuilds ``persons.id`` with the party id as its value
— the original serial values are genuinely gone, and every reference the
downgraded schema recreates is rebuilt from the same source, so the result is
consistent even though it is not byte-identical history.

Revision ID: e3f8c2a91b47
Revises: 29a3872dad10
Create Date: 2026-10-27
"""

import sqlalchemy as sa
from alembic import op

revision = "e3f8c2a91b47"
down_revision = "29a3872dad10"
branch_labels = None
depends_on = None


def _log(message: str) -> None:
    print(f"[party migration] {message}")


DISPLAY_NAME_FALLBACK = "coalesce(nullif(btrim(name), ''), '(unnamed)')"


def upgrade() -> None:
    bind = op.get_bind()

    # --- 1. The club becomes a party -------------------------------------
    bind.execute(sa.text(f"""
        INSERT INTO party (kind, display_name, national_id, email, photo_url)
        SELECT 'association', {DISPLAY_NAME_FALLBACK}, tax_id, email, logo_url
        FROM organization_settings
    """))
    op.add_column("organization_settings", sa.Column("party_id", sa.BigInteger(), nullable=True))
    bind.execute(sa.text("""
        UPDATE organization_settings
        SET party_id = (SELECT max(id) FROM party WHERE kind = 'association')
    """))
    op.alter_column("organization_settings", "party_id", nullable=False)
    op.create_unique_constraint(
        "organization_settings_party_id_key", "organization_settings", ["party_id"]
    )
    op.create_foreign_key(
        "organization_settings_party_id_fkey",
        "organization_settings", "party", ["party_id"], ["id"],
    )

    # --- 2a. addresses: owners become real -------------------------------
    op.add_column("addresses", sa.Column("party_id", sa.BigInteger(), nullable=True))
    op.add_column("addresses", sa.Column("space_id", sa.Integer(), nullable=True))

    orphans = bind.execute(sa.text("""
        DELETE FROM addresses a
        WHERE (a.entity_type = 'person'
               AND NOT EXISTS (SELECT 1 FROM persons p WHERE p.id = a.entity_id))
           OR (a.entity_type = 'space'
               AND NOT EXISTS (SELECT 1 FROM spaces s WHERE s.id = a.entity_id))
           OR (a.entity_type = 'organization'
               AND NOT EXISTS (SELECT 1 FROM organization_settings o WHERE o.id = a.entity_id))
    """)).rowcount
    if orphans:
        _log(f"dropped {orphans} orphaned address rows (owner already deleted)")

    bind.execute(sa.text("""
        UPDATE addresses a SET party_id = p.party_id
        FROM persons p WHERE a.entity_type = 'person' AND a.entity_id = p.id
    """))
    bind.execute(sa.text(
        "UPDATE addresses SET space_id = entity_id WHERE entity_type = 'space'"
    ))
    bind.execute(sa.text("""
        UPDATE addresses a SET party_id = o.party_id
        FROM organization_settings o WHERE a.entity_type = 'organization'
    """))

    op.drop_constraint("valid_entity_type", "addresses", type_="check")
    op.drop_index("idx_addresses_entity", table_name="addresses")
    op.drop_column("addresses", "entity_type")
    op.drop_column("addresses", "entity_id")

    op.create_foreign_key(
        "addresses_party_id_fkey", "addresses", "party",
        ["party_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "addresses_space_id_fkey", "addresses", "spaces",
        ["space_id"], ["id"], ondelete="CASCADE",
    )
    op.create_check_constraint(
        "addresses_exactly_one_owner", "addresses",
        "num_nonnulls(party_id, space_id) = 1",
    )

    # address_types: dead — no endpoint, no UI.
    op.drop_index("idx_addresses_type", table_name="addresses")
    op.drop_constraint("addresses_address_type_id_fkey", "addresses", type_="foreignkey")
    op.drop_column("addresses", "address_type_id")
    op.drop_table("address_types")

    demoted = bind.execute(sa.text("""
        UPDATE addresses SET is_primary = false
        WHERE id IN (
            SELECT id FROM (
                SELECT id, row_number() OVER (
                    PARTITION BY party_id ORDER BY display_order, id
                ) AS rn
                FROM addresses WHERE party_id IS NOT NULL AND is_primary
            ) ranked WHERE rn > 1
        )
    """)).rowcount
    if demoted:
        _log(f"demoted {demoted} duplicate primary addresses (first by display order wins)")

    op.create_index(
        "ix_addresses_party", "addresses", ["party_id"],
        postgresql_where=sa.text("party_id IS NOT NULL"),
    )
    op.create_index(
        "ix_addresses_space", "addresses", ["space_id"],
        postgresql_where=sa.text("space_id IS NOT NULL"),
    )
    op.create_index(
        "uq_addresses_primary_per_party", "addresses", ["party_id"],
        unique=True, postgresql_where=sa.text("party_id IS NOT NULL AND is_primary"),
    )

    # --- 2b. contacts: single-owner, for real -----------------------------
    op.add_column("contacts", sa.Column("party_id", sa.BigInteger(), nullable=True))

    orphans = bind.execute(sa.text("""
        DELETE FROM contacts c
        WHERE NOT EXISTS (SELECT 1 FROM persons p WHERE p.id = c.entity_id)
    """)).rowcount
    if orphans:
        _log(f"dropped {orphans} orphaned contact rows (owner already deleted)")

    bind.execute(sa.text("""
        UPDATE contacts c SET party_id = p.party_id
        FROM persons p WHERE c.entity_id = p.id
    """))

    op.drop_constraint("valid_contact_entity_type", "contacts", type_="check")
    op.drop_index("idx_contacts_entity", table_name="contacts")
    op.drop_column("contacts", "entity_type")
    op.drop_column("contacts", "entity_id")
    op.alter_column("contacts", "party_id", nullable=False)
    op.create_foreign_key(
        "contacts_party_id_fkey", "contacts", "party",
        ["party_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_contacts_party", "contacts", ["party_id"])

    # --- 3. Channels become structural ------------------------------------
    op.create_table(
        "contact_channels",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
    )
    bind.execute(sa.text("""
        INSERT INTO contact_channels (code, name) VALUES
            ('email', 'Email'), ('phone', 'Phone'),
            ('url', 'Website'), ('handle', 'Social handle'),
            ('other', 'Other')
    """))

    op.add_column("contact_types", sa.Column("channel", sa.Text(), nullable=True))
    bind.execute(sa.text("""
        UPDATE contact_types SET channel = split_part(code, '_', 1)
        WHERE split_part(code, '_', 1) IN ('email', 'phone', 'url', 'handle')
    """))
    unguessable = bind.execute(sa.text(
        "UPDATE contact_types SET channel = 'other' WHERE channel IS NULL"
    )).rowcount
    if unguessable:
        _log(f"{unguessable} contact types carry no channel in their code; assigned 'other'")
    op.alter_column("contact_types", "channel", nullable=False)
    op.create_foreign_key(
        "contact_types_channel_fkey", "contact_types", "contact_channels",
        ["channel"], ["code"],
    )
    op.create_unique_constraint(
        "uq_contact_types_id_channel", "contact_types", ["id", "channel"]
    )

    op.add_column("contacts", sa.Column("channel", sa.Text(), nullable=True))
    bind.execute(sa.text("""
        UPDATE contacts c SET channel = ct.channel
        FROM contact_types ct WHERE ct.id = c.contact_type_id
    """))
    # The composite FK replaces the plain one: deleting a type clears both
    # columns, which is what keeps the iff-CHECK below satisfiable.
    op.drop_constraint("contacts_contact_type_id_fkey", "contacts", type_="foreignkey")
    op.create_foreign_key(
        "contacts_channel_matches_type", "contacts", "contact_types",
        ["contact_type_id", "channel"], ["id", "channel"], ondelete="SET NULL",
    )
    op.create_check_constraint(
        "contacts_channel_iff_type", "contacts",
        "(contact_type_id IS NULL) = (channel IS NULL)",
    )

    demoted = bind.execute(sa.text("""
        UPDATE contacts SET is_primary = false
        WHERE id IN (
            SELECT id FROM (
                SELECT id, row_number() OVER (
                    PARTITION BY party_id, channel ORDER BY display_order, id
                ) AS rn
                FROM contacts WHERE is_primary AND channel IS NOT NULL
            ) ranked WHERE rn > 1
        )
    """)).rowcount
    if demoted:
        _log(f"demoted {demoted} duplicate primary contacts (first per channel wins)")

    op.create_index(
        "uq_contacts_one_primary_per_channel", "contacts", ["party_id", "channel"],
        unique=True, postgresql_where=sa.text("is_primary"),
    )

    # --- 4a. The party-level facts leave persons --------------------------
    # The person's values win: they were the live copy — the Phase 1 snapshot
    # on party never saw an edit made since.
    bind.execute(sa.text("""
        UPDATE party pa
        SET email = pe.email, national_id = pe.national_id, photo_url = pe.photo_url
        FROM persons pe
        WHERE pa.id = pe.party_id
          AND (pa.email       IS DISTINCT FROM pe.email
           OR  pa.national_id IS DISTINCT FROM pe.national_id
           OR  pa.photo_url   IS DISTINCT FROM pe.photo_url)
    """))
    op.drop_index("idx_persons_email", table_name="persons")
    op.drop_index("idx_persons_national_id", table_name="persons")
    op.drop_column("persons", "email")
    op.drop_column("persons", "national_id")
    op.drop_column("persons", "photo_url")

    # --- 4b. The primary key hands over -----------------------------------
    op.drop_constraint("members_guardian_party_id_fkey", "members", type_="foreignkey")
    op.drop_constraint("persons_pkey", "persons", type_="primary")
    op.drop_column("persons", "id")
    op.create_primary_key("persons_pkey", "persons", ["party_id"])
    op.drop_constraint("uq_persons_party_id", "persons", type_="unique")
    op.create_foreign_key(
        "members_guardian_party_id_fkey", "members", "persons",
        ["guardian_party_id"], ["party_id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    bind = op.get_bind()

    # --- 4b reversed: persons gets its own serial back --------------------
    # The original id values are gone; the party id is the one consistent
    # substitute, and everything below that reconstructs a reference uses it.
    op.drop_constraint("members_guardian_party_id_fkey", "members", type_="foreignkey")
    op.create_unique_constraint("uq_persons_party_id", "persons", ["party_id"])
    op.drop_constraint("persons_pkey", "persons", type_="primary")
    op.add_column("persons", sa.Column("id", sa.Integer(), nullable=True))
    bind.execute(sa.text("UPDATE persons SET id = party_id"))
    op.alter_column("persons", "id", nullable=False)
    op.create_primary_key("persons_pkey", "persons", ["id"])
    bind.execute(sa.text("CREATE SEQUENCE persons_id_seq OWNED BY persons.id"))
    bind.execute(sa.text(
        "SELECT setval('persons_id_seq', coalesce((SELECT max(id) FROM persons), 0) + 1, false)"
    ))
    bind.execute(sa.text(
        "ALTER TABLE persons ALTER COLUMN id SET DEFAULT nextval('persons_id_seq')"
    ))
    op.create_foreign_key(
        "members_guardian_party_id_fkey", "members", "persons",
        ["guardian_party_id"], ["party_id"], ondelete="SET NULL",
    )

    # --- 4a reversed: copy the facts back down ----------------------------
    op.add_column("persons", sa.Column("email", sa.String(255), nullable=True))
    op.add_column("persons", sa.Column("national_id", sa.String(50), nullable=True))
    op.add_column("persons", sa.Column("photo_url", sa.String(500), nullable=True))
    bind.execute(sa.text("""
        UPDATE persons pe
        SET email = pa.email, national_id = pa.national_id, photo_url = pa.photo_url
        FROM party pa WHERE pa.id = pe.party_id
    """))
    op.create_index(
        "idx_persons_email", "persons", ["email"],
        postgresql_where=sa.text("email IS NOT NULL"),
    )
    op.create_index(
        "idx_persons_national_id", "persons", ["national_id"],
        postgresql_where=sa.text("national_id IS NOT NULL"),
    )

    # --- 3 reversed --------------------------------------------------------
    op.drop_index("uq_contacts_one_primary_per_channel", table_name="contacts")
    op.drop_constraint("contacts_channel_iff_type", "contacts", type_="check")
    op.drop_constraint("contacts_channel_matches_type", "contacts", type_="foreignkey")
    op.create_foreign_key(
        "contacts_contact_type_id_fkey", "contacts", "contact_types",
        ["contact_type_id"], ["id"], ondelete="SET NULL",
    )
    op.drop_column("contacts", "channel")
    op.drop_constraint("uq_contact_types_id_channel", "contact_types", type_="unique")
    op.drop_constraint("contact_types_channel_fkey", "contact_types", type_="foreignkey")
    op.drop_column("contact_types", "channel")
    op.drop_table("contact_channels")

    # --- 2b reversed -------------------------------------------------------
    op.drop_index("ix_contacts_party", table_name="contacts")
    op.add_column("contacts", sa.Column("entity_type", sa.String(30), nullable=True))
    op.add_column("contacts", sa.Column("entity_id", sa.Integer(), nullable=True))
    bind.execute(sa.text(
        "UPDATE contacts SET entity_type = 'person', entity_id = party_id"
    ))
    op.alter_column("contacts", "entity_type", nullable=False)
    op.alter_column("contacts", "entity_id", nullable=False)
    op.drop_constraint("contacts_party_id_fkey", "contacts", type_="foreignkey")
    op.drop_column("contacts", "party_id")
    op.create_check_constraint(
        "valid_contact_entity_type", "contacts", "entity_type IN ('person')"
    )
    op.create_index("idx_contacts_entity", "contacts", ["entity_type", "entity_id"])

    # --- 2a reversed -------------------------------------------------------
    op.create_table(
        "address_types",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("description", sa.String(255)),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("display_order", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.add_column("addresses", sa.Column("address_type_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "addresses_address_type_id_fkey", "addresses", "address_types",
        ["address_type_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("idx_addresses_type", "addresses", ["address_type_id"])

    op.drop_index("uq_addresses_primary_per_party", table_name="addresses")
    op.drop_index("ix_addresses_space", table_name="addresses")
    op.drop_index("ix_addresses_party", table_name="addresses")
    op.add_column("addresses", sa.Column("entity_type", sa.String(30), nullable=True))
    op.add_column("addresses", sa.Column("entity_id", sa.Integer(), nullable=True))
    bind.execute(sa.text("""
        UPDATE addresses a SET entity_type = 'person', entity_id = a.party_id
        WHERE a.party_id IS NOT NULL
          AND EXISTS (SELECT 1 FROM persons p WHERE p.party_id = a.party_id)
    """))
    bind.execute(sa.text("""
        UPDATE addresses a SET entity_type = 'organization', entity_id = o.id
        FROM organization_settings o
        WHERE a.party_id = o.party_id
    """))
    bind.execute(sa.text("""
        UPDATE addresses SET entity_type = 'space', entity_id = space_id
        WHERE space_id IS NOT NULL
    """))
    op.alter_column("addresses", "entity_type", nullable=False)
    op.alter_column("addresses", "entity_id", nullable=False)
    op.drop_constraint("addresses_exactly_one_owner", "addresses", type_="check")
    op.drop_constraint("addresses_space_id_fkey", "addresses", type_="foreignkey")
    op.drop_constraint("addresses_party_id_fkey", "addresses", type_="foreignkey")
    op.drop_column("addresses", "space_id")
    op.drop_column("addresses", "party_id")
    op.create_check_constraint(
        "valid_entity_type", "addresses",
        "entity_type IN ('person', 'organization', 'space')",
    )
    op.create_index("idx_addresses_entity", "addresses", ["entity_type", "entity_id"])

    # --- 1 reversed ---------------------------------------------------------
    op.drop_constraint("organization_settings_party_id_fkey", "organization_settings", type_="foreignkey")
    op.drop_constraint("organization_settings_party_id_key", "organization_settings", type_="unique")
    op.drop_column("organization_settings", "party_id")
    bind.execute(sa.text("DELETE FROM party WHERE kind = 'association'"))
