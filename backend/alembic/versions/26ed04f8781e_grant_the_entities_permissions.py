"""Grant the entities permissions to the admin system role.

Phase 5b of the party refactor (ADR 0003) adds the entities screens — the
non-person parties (companies, public bodies, foundations, associations) a
receipt or mandate can be addressed to. They get a dedicated permission pair,
`entities.read` / `entities.write`, so a custom role can manage entities
without seeing members (or vice versa).

The permission catalog lives in code (`app.core.permissions`); the stored
grants live in `role_permissions` and were seeded by the roles migration with
a frozen key list, so every later addition lands by its own migration. The
`admin` system role gains both keys here, matching the catalog's intent that
admin holds everything non-reserved; `super_admin` bypasses `role_permissions`
entirely and needs no rows. Custom roles are left alone — granting them is the
role author's call.

Revision ID: 26ed04f8781e
Revises: e9b7d4c15f28
Create Date: 2026-10-28
"""

import sqlalchemy as sa
from alembic import op

revision = "26ed04f8781e"
down_revision = "e9b7d4c15f28"
branch_labels = None
depends_on = None

ENTITY_KEYS = ("entities.read", "entities.write")


def upgrade() -> None:
    conn = op.get_bind()
    for key in ENTITY_KEYS:
        conn.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_key) "
                "SELECT id, :key FROM roles WHERE slug = 'admin' "
                "AND NOT EXISTS (SELECT 1 FROM role_permissions rp "
                "WHERE rp.role_id = roles.id AND rp.permission_key = :key)"
            ),
            {"key": key},
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_key IN :keys"
        ).bindparams(sa.bindparam("keys", expanding=True)),
        {"keys": list(ENTITY_KEYS)},
    )
