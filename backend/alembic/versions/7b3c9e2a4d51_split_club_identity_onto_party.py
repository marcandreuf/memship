"""Split club identity onto the party; bank details become bank_accounts.

Phase 5c of the party refactor (ADR 0003). `organization_settings` stops
doing two jobs: the club's identity facts move onto its party (name, legal
name, tax id, email, logo into party columns; phone and website into the
party's primary contacts), and bank details stop being columns anywhere —
a new party-scoped `bank_accounts` table (the addresses/contacts shape, one
primary per party) absorbs both the club's collection account and every
person's debit account. `creditor_id` and `brand_color` stay on settings:
one is the SEPA creditor scheme identifier and the other is instance
branding, neither an identity fact any party could hold.

The club copy direction matters: settings values win over the party's
Phase 3 copies, because settings held the live values the screens edited
while the party copies were written once at creation and never synced.

The downgrade restores every column from the party, its contacts and the
primary accounts, deletes the rows the upgrade created, and logs what it
cannot represent (an entity's account or legal name has no home in the old
schema) before dropping it — losses are detected, deterministic and logged,
per the data policy.

Revision ID: 7b3c9e2a4d51
Revises: 26ed04f8781e
Create Date: 2026-10-28
"""

import sqlalchemy as sa
from alembic import op

revision = "7b3c9e2a4d51"
down_revision = "26ed04f8781e"
branch_labels = None
depends_on = None


def _log(message: str) -> None:
    print(f"[party migration] {message}")


CLUB_CONTACT_TYPES = (("phone", "phone_main", "Main Phone"), ("url", "website", "Website"))


def upgrade() -> None:
    conn = op.get_bind()

    op.add_column("party", sa.Column("legal_name", sa.String(255), nullable=True))

    op.create_table(
        "bank_accounts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("party_id", sa.BigInteger(), nullable=False),
        sa.Column("bank_name", sa.String(255), nullable=True),
        sa.Column("iban", sa.String(34), nullable=True),
        sa.Column("bic", sa.String(11), nullable=True),
        sa.Column("holder_name", sa.String(255), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["party_id"], ["party.id"],
            name="bank_accounts_party_id_fkey", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_bank_accounts_party", "bank_accounts", ["party_id"])
    op.create_index(
        "uq_bank_accounts_primary_per_party",
        "bank_accounts",
        ["party_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )

    # The club: settings values overwrite the party's stale creation-time copies.
    conn.execute(sa.text(
        """
        UPDATE party p
        SET display_name = o.name,
            legal_name = o.legal_name,
            national_id = o.tax_id,
            email = o.email,
            photo_url = o.logo_url,
            updated_at = now()
        FROM organization_settings o
        WHERE p.id = o.party_id
        """
    ))

    # The club's phone and website become its primary contacts. The types are
    # created if missing, same codes the model's insert event uses.
    for channel, code, name in CLUB_CONTACT_TYPES:
        conn.execute(sa.text(
            "INSERT INTO contact_channels (code, name) VALUES (:ch, :name) "
            "ON CONFLICT (code) DO NOTHING"
        ), {"ch": channel, "name": name})
        conn.execute(sa.text(
            "INSERT INTO contact_types (code, name, channel, is_active, display_order) "
            "SELECT :code, :name, :ch, true, 0 "
            "WHERE NOT EXISTS (SELECT 1 FROM contact_types WHERE code = :code)"
        ), {"code": code, "name": name, "ch": channel})

    moved_contacts = 0
    for channel, code, settings_col in (
        ("phone", "phone_main", "phone"),
        ("url", "website", "website"),
    ):
        moved_contacts += conn.execute(sa.text(
            f"""
            INSERT INTO contacts (party_id, contact_type_id, channel, value,
                                  is_primary, display_order, is_active)
            SELECT o.party_id, ct.id, :ch, o.{settings_col}, true, 0, true
            FROM organization_settings o
            JOIN contact_types ct ON ct.code = :code
            WHERE COALESCE(o.{settings_col}, '') <> ''
            """
        ), {"ch": channel, "code": code}).rowcount
    _log(f"club contacts: created {moved_contacts} rows from settings phone/website")

    club_accounts = conn.execute(sa.text(
        """
        INSERT INTO bank_accounts (party_id, bank_name, iban, bic, is_primary)
        SELECT o.party_id, o.bank_name, o.bank_iban, o.bank_bic, true
        FROM organization_settings o
        WHERE COALESCE(o.bank_name, '') <> ''
           OR COALESCE(o.bank_iban, '') <> ''
           OR COALESCE(o.bank_bic, '') <> ''
        """
    )).rowcount
    person_accounts = conn.execute(sa.text(
        """
        INSERT INTO bank_accounts (party_id, iban, bic, holder_name, is_primary)
        SELECT p.party_id, p.bank_iban, p.bank_bic, p.bank_holder_name, true
        FROM persons p
        WHERE COALESCE(p.bank_iban, '') <> ''
           OR COALESCE(p.bank_bic, '') <> ''
           OR COALESCE(p.bank_holder_name, '') <> ''
        """
    )).rowcount
    _log(f"bank_accounts: {club_accounts} club + {person_accounts} person rows")

    for col in ("name", "legal_name", "email", "phone", "website",
                "logo_url", "tax_id", "bank_name", "bank_iban", "bank_bic"):
        op.drop_column("organization_settings", col)
    for col in ("bank_iban", "bank_bic", "bank_holder_name"):
        op.drop_column("persons", col)


def downgrade() -> None:
    conn = op.get_bind()

    # What the old schema cannot hold is dropped with a count, not silently:
    # accounts and legal names of parties that are neither persons nor the club.
    orphans = conn.execute(sa.text(
        """
        SELECT count(*) FROM bank_accounts b
        WHERE NOT EXISTS (SELECT 1 FROM persons p WHERE p.party_id = b.party_id)
          AND NOT EXISTS (SELECT 1 FROM organization_settings o WHERE o.party_id = b.party_id)
        """
    )).scalar_one()
    if orphans:
        _log(f"downgrade: dropping {orphans} bank account(s) with no home in the old schema")
    entity_legal_names = conn.execute(sa.text(
        """
        SELECT count(*) FROM party p
        WHERE p.legal_name IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM organization_settings o WHERE o.party_id = p.id)
        """
    )).scalar_one()
    if entity_legal_names:
        _log(f"downgrade: dropping legal_name on {entity_legal_names} non-club part(ies)")

    op.add_column("organization_settings", sa.Column("name", sa.String(255), nullable=True))
    for col, size in (("legal_name", 255), ("email", 255), ("phone", 50),
                      ("website", 255), ("logo_url", 500), ("tax_id", 50),
                      ("bank_name", 255), ("bank_iban", 34), ("bank_bic", 11)):
        op.add_column("organization_settings", sa.Column(col, sa.String(size), nullable=True))
    for col, size in (("bank_iban", 34), ("bank_bic", 11), ("bank_holder_name", 255)):
        op.add_column("persons", sa.Column(col, sa.String(size), nullable=True))

    conn.execute(sa.text(
        """
        UPDATE organization_settings o
        SET name = COALESCE(p.display_name, '(unnamed)'),
            legal_name = p.legal_name,
            email = p.email,
            tax_id = p.national_id,
            logo_url = p.photo_url,
            phone = (SELECT c.value FROM contacts c
                     WHERE c.party_id = o.party_id AND c.channel = 'phone'
                       AND c.is_primary AND c.is_active LIMIT 1),
            website = (SELECT c.value FROM contacts c
                       WHERE c.party_id = o.party_id AND c.channel = 'url'
                         AND c.is_primary AND c.is_active LIMIT 1),
            bank_name = b.bank_name,
            bank_iban = b.iban,
            bank_bic = b.bic
        FROM party p
        LEFT JOIN bank_accounts b ON b.party_id = p.id AND b.is_primary
        WHERE p.id = o.party_id
        """
    ))
    op.alter_column("organization_settings", "name", nullable=False)

    conn.execute(sa.text(
        """
        UPDATE persons p
        SET bank_iban = b.iban,
            bank_bic = b.bic,
            bank_holder_name = b.holder_name
        FROM bank_accounts b
        WHERE b.party_id = p.party_id AND b.is_primary
        """
    ))

    # The contact rows the upgrade created go away with their columns restored.
    removed = conn.execute(sa.text(
        """
        DELETE FROM contacts c
        USING organization_settings o
        WHERE c.party_id = o.party_id
          AND c.channel IN ('phone', 'url')
          AND c.is_primary
        """
    )).rowcount
    if removed:
        _log(f"downgrade: removed {removed} club contact row(s)")

    op.drop_index("uq_bank_accounts_primary_per_party", table_name="bank_accounts")
    op.drop_index("ix_bank_accounts_party", table_name="bank_accounts")
    op.drop_table("bank_accounts")
    op.drop_column("party", "legal_name")
