"""Allow 'queued' on receipt_reminders.status

Revision ID: 9c1d2e3f4a5b
Revises: d0e1f2a3b4c5
Create Date: 2026-09-12

The admin's "send reminder" button used to send the email inside the request
and write the row with the outcome. It now writes the row as ``queued`` and a
Celery task delivers the email after the commit, recording ``sent`` or
``failed`` on the same row.
"""

from alembic import op

revision = "9c1d2e3f4a5b"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("valid_receipt_reminder_status", "receipt_reminders", type_="check")
    op.create_check_constraint(
        "valid_receipt_reminder_status",
        "receipt_reminders",
        "status IN ('queued', 'sent', 'failed', 'skipped')",
    )


def downgrade() -> None:
    # A row still in flight has no place in the old set; call it failed.
    op.execute("UPDATE receipt_reminders SET status = 'failed' WHERE status = 'queued'")
    op.drop_constraint("valid_receipt_reminder_status", "receipt_reminders", type_="check")
    op.create_check_constraint(
        "valid_receipt_reminder_status",
        "receipt_reminders",
        "status IN ('sent', 'failed', 'skipped')",
    )
