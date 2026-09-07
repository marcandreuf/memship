"""add_default_membership_type

Marks the membership type new sign-ups land on, and guarantees every install
has one. Before this, both registration paths took the oldest active row, which
on a seeded install is the 50 EUR/month plan — so self-registering silently
started a recurring fee.

An existing free tier is promoted rather than replaced. When a club has none,
one is created: leaving no default would put NULL on new members' membership
type, and activities that restrict allowed membership types reject a NULL
member outright — a worse regression than the bug being fixed.

No member row is touched. Members already sitting on a paid tier they never
chose are a separate clean-up, deliberately left to a human.

Revision ID: a5b6c7d8e9f0
Revises: a4b5c6d7e8f9
Create Date: 2026-09-07 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a5b6c7d8e9f0'
down_revision: Union[str, None] = 'a4b5c6d7e8f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FALLBACK_NAME = "Registered"
FALLBACK_SLUG = "registered"
FALLBACK_DESCRIPTION = (
    "Free tier every new sign-up lands on until an administrator "
    "moves them to a paid plan"
)


def upgrade() -> None:
    op.add_column(
        'membership_types',
        sa.Column(
            'is_default',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
        ),
    )
    op.create_index(
        'uq_membership_types_is_default',
        'membership_types',
        ['is_default'],
        unique=True,
        postgresql_where=sa.text('is_default'),
    )
    op.create_check_constraint(
        'default_membership_type_is_free',
        'membership_types',
        'NOT is_default OR coalesce(base_price, 0) = 0',
    )

    conn = op.get_bind()
    # Active first, then the club's own ordering, then id — so two free tiers
    # resolve the same way on every replica of the same database.
    promoted = conn.execute(
        sa.text(
            """
            UPDATE membership_types SET is_default = true WHERE id = (
                SELECT id FROM membership_types
                WHERE coalesce(base_price, 0) = 0
                ORDER BY is_active DESC NULLS LAST,
                         display_order NULLS LAST,
                         id
                LIMIT 1
            )
            """
        )
    ).rowcount
    if promoted:
        return

    name, slug = FALLBACK_NAME, FALLBACK_SLUG
    suffix = 1
    while conn.execute(
        sa.text(
            "SELECT 1 FROM membership_types WHERE name = :name OR slug = :slug"
        ),
        {"name": name, "slug": slug},
    ).first():
        suffix += 1
        name, slug = f"{FALLBACK_NAME} {suffix}", f"{FALLBACK_SLUG}-{suffix}"

    conn.execute(
        sa.text(
            """
            INSERT INTO membership_types
                (name, slug, description, base_price, billing_frequency,
                 display_order, is_active, is_default)
            VALUES
                (:name, :slug, :description, 0, 'annual', 0, true, true)
            """
        ),
        {"name": name, "slug": slug, "description": FALLBACK_DESCRIPTION},
    )


def downgrade() -> None:
    # A tier created on the way up stays: members may already point at it.
    op.drop_constraint(
        'default_membership_type_is_free', 'membership_types', type_='check'
    )
    op.drop_index('uq_membership_types_is_default', table_name='membership_types')
    op.drop_column('membership_types', 'is_default')
