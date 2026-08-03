"""add roles and permissions

Revision ID: d1a2b3c4e5f6
Revises: c5d6e7f8a9b0
Create Date: 2026-08-02

Creates the role tables, backfills assignments from ``users.role``, then drops
``users.role`` and the unused ``users.permissions`` column.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d1a2b3c4e5f6"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SUPER_ADMIN_KEYS: set[str] = set()

RESERVED_KEYS = {"roles.write", "settings.integrations.write"}

ADMINISTRATIVE_KEYS = {
    "members.read",
    "members.write",
    "members.approve",
    "membership.read",
    "membership.write",
    "activities.read",
    "activities.write",
    "activities.publish",
    "registrations.read",
    "registrations.write",
    "billing.read",
    "billing.write",
    "billing.run",
    "communications.read",
    "communications.write",
    "communications.send",
    "bookings.read",
    "bookings.write",
    "reports.read",
    "reminders.read",
    "reminders.write",
    "settings.read",
    "settings.write",
    "settings.custom_fields.write",
    "settings.integrations.write",
    "users.read",
    "users.write",
    "roles.read",
    "roles.write",
}

SELF_KEYS = {
    "self.profile.read",
    "self.profile.write",
    "self.activities.read",
    "self.registrations.read",
    "self.registrations.write",
    "self.billing.read",
    "self.billing.write",
    "self.card.read",
    "self.bookings.read",
    "self.bookings.write",
    "self.communications.read",
    "self.communications.write",
}

ADMIN_KEYS = (ADMINISTRATIVE_KEYS | SELF_KEYS) - RESERVED_KEYS - {
    "settings.custom_fields.write"
}


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("idx_roles_slug", "roles", ["slug"])

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_key", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission_key"),
    )
    op.create_index("idx_role_permissions_role", "role_permissions", ["role_id"])

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column(
            "assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("assigned_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )
    op.create_index("idx_user_roles_user", "user_roles", ["user_id"])

    conn = op.get_bind()

    role_ids: dict[str, int] = {}
    for slug, name, keys in (
        ("super_admin", "Super Admin", SUPER_ADMIN_KEYS),
        ("admin", "Administrator", ADMIN_KEYS),
        ("member", "Member", SELF_KEYS),
    ):
        role_ids[slug] = conn.execute(
            sa.text(
                "INSERT INTO roles (slug, name, is_system) "
                "VALUES (:slug, :name, true) RETURNING id"
            ),
            {"slug": slug, "name": name},
        ).scalar_one()
        for key in sorted(keys):
            conn.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_key) "
                    "VALUES (:role_id, :key)"
                ),
                {"role_id": role_ids[slug], "key": key},
            )

    conn.execute(
        sa.text(
            "INSERT INTO user_roles (user_id, role_id) "
            "SELECT id, :member_id FROM users"
        ),
        {"member_id": role_ids["member"]},
    )

    for legacy_role in ("super_admin", "admin"):
        conn.execute(
            sa.text(
                "INSERT INTO user_roles (user_id, role_id) "
                "SELECT id, :role_id FROM users WHERE role = :legacy"
            ),
            {"role_id": role_ids[legacy_role], "legacy": legacy_role},
        )

    unexpected = conn.execute(
        sa.text(
            "SELECT email, role FROM users "
            "WHERE role NOT IN ('super_admin', 'admin', 'member') ORDER BY email"
        )
    ).fetchall()
    for email, legacy_role in unexpected:
        print(
            f"[roles migration] {email} had role '{legacy_role}' and was mapped to "
            f"'member' only. Assign a role explicitly if it needs staff access."
        )

    orphans = conn.execute(
        sa.text(
            "SELECT count(*) FROM users u "
            "WHERE NOT EXISTS (SELECT 1 FROM user_roles r WHERE r.user_id = u.id)"
        )
    ).scalar_one()
    if orphans:
        raise RuntimeError(f"{orphans} user(s) ended the migration with no role")

    op.drop_constraint("valid_role", "users", type_="check")
    op.drop_column("users", "role")
    # Never read anywhere; predates the catalog and would now be mistaken for it.
    op.drop_column("users", "permissions")


def downgrade() -> None:
    # Lossy: a user holding several roles collapses to the most privileged one.
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=50), nullable=False, server_default="member"),
    )
    op.add_column(
        "users", sa.Column("permissions", postgresql.JSONB(), nullable=True)
    )
    conn = op.get_bind()
    for slug in ("admin", "super_admin"):
        conn.execute(
            sa.text(
                "UPDATE users SET role = :slug WHERE id IN ("
                "  SELECT ur.user_id FROM user_roles ur"
                "  JOIN roles r ON r.id = ur.role_id WHERE r.slug = :slug)"
            ),
            {"slug": slug},
        )
    op.create_check_constraint(
        "valid_role",
        "users",
        "role IN ('super_admin', 'admin', 'restricted', 'member')",
    )

    op.drop_index("idx_user_roles_user", table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_index("idx_role_permissions_role", table_name="role_permissions")
    op.drop_table("role_permissions")
    op.drop_index("idx_roles_slug", table_name="roles")
    op.drop_table("roles")
