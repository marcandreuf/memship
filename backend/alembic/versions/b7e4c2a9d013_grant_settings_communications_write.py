"""Grant settings.communications.write to the admin system role.

Choosing which emails the club sends used to sit behind
`settings.integrations.write`, which is reserved to the super admin because it
also guards credentials (SSO, mail transport, payment gateways). The email
switches hold no credential, and a club admin needs them to turn on automatic
cancellation of unpaid seats (#591), so they get a non-reserved key of their
own. The `admin` system role gains it here, as every non-reserved key it is
meant to hold; `super_admin` bypasses `role_permissions`. Custom roles are left
alone — granting them is the role author's call.

Revision ID: b7e4c2a9d013
Revises: a3d9e2c71f48
Create Date: 2026-11-19
"""

import sqlalchemy as sa
from alembic import op

revision = "b7e4c2a9d013"
down_revision = "a3d9e2c71f48"
branch_labels = None
depends_on = None

KEY = "settings.communications.write"


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_key) "
            "SELECT id, :key FROM roles WHERE slug = 'admin' "
            "AND NOT EXISTS (SELECT 1 FROM role_permissions rp "
            "WHERE rp.role_id = roles.id AND rp.permission_key = :key)"
        ),
        {"key": KEY},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM role_permissions WHERE permission_key = :key"), {"key": KEY}
    )
