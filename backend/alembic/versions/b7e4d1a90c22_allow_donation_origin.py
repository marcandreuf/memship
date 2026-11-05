"""Allow 'donation' on receipts.origin and concepts.concept_type

Revision ID: b7e4d1a90c22
Revises: 642cb41348f9
Create Date: 2026-11-05

A donation had nowhere to say it was one. It went in as ``manual`` beside every
other hand-made charge, and the only thing telling them apart was free text in
``description``, so "how much did we raise in donations" was reading
descriptions and hoping whoever typed them was consistent (#432).

The downgrade reclassifies donations as ``manual`` rather than deleting them: a
receipt is an accounting record, and losing one to a schema rollback is worse
than losing its classification. It is lossy in one direction only, which is why
the upgrade does not try to find donations already recorded as ``manual`` --
nothing can tell them apart from any other manual charge.
"""

from alembic import op

revision = "b7e4d1a90c22"
down_revision = "642cb41348f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("valid_receipt_origin", "receipts", type_="check")
    op.create_check_constraint(
        "valid_receipt_origin",
        "receipts",
        "origin IN ('membership', 'activity', 'booking', 'manual', 'service', 'donation')",
    )
    op.drop_constraint("valid_concept_type", "concepts", type_="check")
    op.create_check_constraint(
        "valid_concept_type",
        "concepts",
        "concept_type IN ('membership', 'activity', 'booking', 'manual', 'service', "
        "'donation')",
    )


def downgrade() -> None:
    op.execute("UPDATE receipts SET origin = 'manual' WHERE origin = 'donation'")
    op.execute("UPDATE concepts SET concept_type = 'manual' WHERE concept_type = 'donation'")
    op.drop_constraint("valid_receipt_origin", "receipts", type_="check")
    op.create_check_constraint(
        "valid_receipt_origin",
        "receipts",
        "origin IN ('membership', 'activity', 'booking', 'manual', 'service')",
    )
    op.drop_constraint("valid_concept_type", "concepts", type_="check")
    op.create_check_constraint(
        "valid_concept_type",
        "concepts",
        "concept_type IN ('membership', 'activity', 'booking', 'manual', 'service')",
    )
