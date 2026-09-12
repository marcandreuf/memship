"""Take staff accounts out of the club's member register

Revision ID: e2f3a4b5c6d7
Revises: 9c1d2e3f4a5b
Create Date: 2026-09-12

`member` used to be pinned to every account, so a super admin or club admin
carried a member number, a membership type and a place in every member count,
export and billing run. It is opt-in now (#168), and staff accounts are seeded
without it — this brings the accounts an existing install already has into
line: the member record goes, and with it the `member` role assignment.

A member row is left alone when a receipt or a SEPA mandate points at it.
Those two are the references that would make the delete fail outright, and an
account with billing history behind it is one a person should look at rather
than one a migration should quietly rewrite. Bookings, registrations and
announcement recipients cascade with the row.

The role assignment is removed only for an account whose member row actually
went, so the pair stays consistent either way, and only where a staff role
remains, so no account is left holding nothing.
"""

from alembic import op

revision = "e2f3a4b5c6d7"
down_revision = "9c1d2e3f4a5b"
branch_labels = None
depends_on = None

STAFF_SLUGS = "('super_admin', 'admin')"


def upgrade() -> None:
    op.execute(
        f"""
        DELETE FROM members m
        USING users u, user_roles ur, roles r
        WHERE m.user_id = u.id
          AND ur.user_id = u.id
          AND ur.role_id = r.id
          AND r.slug IN {STAFF_SLUGS}
          AND NOT EXISTS (SELECT 1 FROM receipts x WHERE x.member_id = m.id)
          AND NOT EXISTS (SELECT 1 FROM sepa_mandates x WHERE x.member_id = m.id)
        """
    )

    op.execute(
        f"""
        DELETE FROM user_roles ur
        USING roles r
        WHERE ur.role_id = r.id
          AND r.slug = 'member'
          AND EXISTS (
              SELECT 1 FROM user_roles s
              JOIN roles sr ON sr.id = s.role_id
              WHERE s.user_id = ur.user_id AND sr.slug IN {STAFF_SLUGS}
          )
          AND NOT EXISTS (
              SELECT 1 FROM members m WHERE m.user_id = ur.user_id
          )
        """
    )


def downgrade() -> None:
    # The member rows cannot come back — their numbers were released and the
    # rows that cascaded with them are gone. Restoring the role assignment is
    # the half that is reversible, and it is what the old code would have
    # re-added on the next write anyway.
    op.execute(
        f"""
        INSERT INTO user_roles (user_id, role_id)
        SELECT DISTINCT s.user_id, r.id
        FROM user_roles s
        JOIN roles sr ON sr.id = s.role_id
        CROSS JOIN roles r
        WHERE sr.slug IN {STAFF_SLUGS}
          AND r.slug = 'member'
          AND NOT EXISTS (
              SELECT 1 FROM user_roles e
              WHERE e.user_id = s.user_id AND e.role_id = r.id
          )
        """
    )
