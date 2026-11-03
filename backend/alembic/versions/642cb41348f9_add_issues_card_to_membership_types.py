"""Issue the member card per membership type

Revision ID: 642cb41348f9
Revises: 5420c00e66da
Create Date: 2026-11-03

`features.member_card` was one switch for the whole instance, so an
organisation with a free supporter tier beside a paid one could not withhold
the card from the free tier — and the card is what the paid tier is buying
(#428 Part 2).

**Off for every type, including existing ones.** That is the decision, and it
is the opposite of a default that preserves current behaviour: a card issued to
everyone is precisely what this exists to stop, so backfilling `true` would
ship the feature switched off in practice.

The consequence belongs in the release notes of whatever version carries this:

    An instance running with `features.member_card` on today stops issuing
    cards on upgrade, until an admin ticks the types that should have them.

This sits *beneath* `features.member_card` rather than replacing it. Two levels
with distinct meanings: the flag answers whether the card module exists on this
instance at all and keeps answering 404 for all seven card endpoints when off,
this answers whether a given member gets one.

The downgrade drops the column, after which every member of an enabled instance
is issued a card again — the pre-#428 behaviour, so a downgraded instance is
permissive rather than broken.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '642cb41348f9'
down_revision: Union[str, None] = '5420c00e66da'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "membership_types",
        sa.Column(
            "issues_card", sa.Boolean(), server_default="false", nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("membership_types", "issues_card")
