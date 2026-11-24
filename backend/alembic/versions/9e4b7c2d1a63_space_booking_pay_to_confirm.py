"""Let a paid space booking wait for its payment (#603)

Revision ID: 9e4b7c2d1a63
Revises: c4f8a1d27e90
Create Date: 2026-11-23

The space side mirrors what #591 gave activities.

``spaces.payment_flow``: ``legacy`` books a slot at once and bills it afterwards,
``pay_to_confirm`` holds the booking as ``pending`` until its receipt is paid. Every
space that exists when this runs is stamped ``legacy``, so nothing already running
changes behaviour, and the server default then becomes ``pay_to_confirm`` for new
spaces. Unlike an activity's, a space's flow may later be switched from ``legacy`` to
``pay_to_confirm``, never back. ``payment_methods`` and the auto-cancel override are
the activity's columns, NULL to inherit the club.

``bookings`` gains the ``pending`` status, which also enters the partial unique index:
without it a member could hold a pending row and a booked one for the same slot. A
pending booking always has a deadline (``payment_due_at``) and remembers when the
hold began (``pending_since``), which is what the reminder window is measured from.
The rest are the registration's columns for the reminder, the cause of a cancellation
the system made, a late payment and a refund owed. The partial index serves the
sweep, which reads pending rows by deadline.

Existing bookings take the defaults: none is pending, none was reminded, released by
a sweep or paid late, and none owes a refund the club has not already settled. The
downgrade refuses while a booking is pending, since the old status check would not
hold it, and otherwise drops everything it added.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "9e4b7c2d1a63"
down_revision = "c4f8a1d27e90"
branch_labels = None
depends_on = None

OLD_STATUSES = "('booked', 'waitlisted', 'cancelled')"
NEW_STATUSES = "('booked', 'waitlisted', 'cancelled', 'pending')"


def upgrade() -> None:
    op.add_column(
        "spaces",
        sa.Column(
            "payment_flow", sa.String(length=20), nullable=False, server_default="legacy"
        ),
    )
    op.alter_column("spaces", "payment_flow", server_default="pay_to_confirm")
    op.add_column(
        "spaces",
        sa.Column(
            "payment_methods",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column("spaces", sa.Column("auto_cancel_enabled", sa.Boolean()))
    op.add_column("spaces", sa.Column("auto_cancel_hours", sa.Integer()))
    op.create_check_constraint(
        "valid_space_payment_flow",
        "spaces",
        "payment_flow IN ('legacy', 'pay_to_confirm')",
    )
    op.create_check_constraint(
        "valid_space_payment_methods",
        "spaces",
        "payment_methods <@ ARRAY['card', 'bizum', 'transfer', 'cash']::varchar[]",
    )

    op.drop_constraint("booking_status_valid", "bookings", type_="check")
    op.create_check_constraint(
        "booking_status_valid", "bookings", f"status IN {NEW_STATUSES}"
    )
    op.drop_index("uq_bookings_party_slot_active", table_name="bookings")
    op.create_index(
        "uq_bookings_party_slot_active",
        "bookings",
        ["space_slot_id", "party_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('booked', 'waitlisted', 'pending')"),
    )

    for name in (
        "payment_due_at",
        "pending_since",
        "payment_reminder_sent_at",
        "late_payment_at",
        "late_payment_seen_at",
        "refund_returned_at",
    ):
        op.add_column("bookings", sa.Column(name, sa.DateTime(timezone=True)))
    op.add_column("bookings", sa.Column("cancelled_cause", sa.String(length=30)))
    op.add_column(
        "bookings",
        sa.Column(
            "refund_status", sa.String(length=20), nullable=False, server_default="none"
        ),
    )
    op.add_column("bookings", sa.Column("refund_returned_by", sa.Integer()))
    op.add_column("bookings", sa.Column("refund_credit_note_id", sa.Integer()))
    op.create_foreign_key(
        "fk_bookings_refund_returned_by",
        "bookings",
        "users",
        ["refund_returned_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_bookings_refund_credit_note_id",
        "bookings",
        "receipts",
        ["refund_credit_note_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "valid_booking_refund_status",
        "bookings",
        "refund_status IN ('none', 'due', 'returned')",
    )
    op.create_check_constraint(
        "valid_booking_cancelled_cause",
        "bookings",
        "cancelled_cause IN ('payment_expired')",
    )
    op.create_index(
        "idx_bookings_pending_due",
        "bookings",
        ["payment_due_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    pending = op.get_bind().execute(
        sa.text("SELECT count(*) FROM bookings WHERE status = 'pending'")
    ).scalar()
    if pending:
        raise RuntimeError(
            f"{pending} booking(s) are pending payment; confirm or cancel them "
            "before downgrading"
        )

    op.drop_index("idx_bookings_pending_due", table_name="bookings")
    op.drop_constraint("valid_booking_cancelled_cause", "bookings", type_="check")
    op.drop_constraint("valid_booking_refund_status", "bookings", type_="check")
    op.drop_constraint(
        "fk_bookings_refund_credit_note_id", "bookings", type_="foreignkey"
    )
    op.drop_constraint("fk_bookings_refund_returned_by", "bookings", type_="foreignkey")
    for name in (
        "refund_credit_note_id",
        "refund_returned_by",
        "refund_status",
        "cancelled_cause",
        "refund_returned_at",
        "late_payment_seen_at",
        "late_payment_at",
        "payment_reminder_sent_at",
        "pending_since",
        "payment_due_at",
    ):
        op.drop_column("bookings", name)

    op.drop_index("uq_bookings_party_slot_active", table_name="bookings")
    op.create_index(
        "uq_bookings_party_slot_active",
        "bookings",
        ["space_slot_id", "party_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('booked', 'waitlisted')"),
    )
    op.drop_constraint("booking_status_valid", "bookings", type_="check")
    op.create_check_constraint(
        "booking_status_valid", "bookings", f"status IN {OLD_STATUSES}"
    )

    op.drop_constraint("valid_space_payment_methods", "spaces", type_="check")
    op.drop_constraint("valid_space_payment_flow", "spaces", type_="check")
    op.drop_column("spaces", "auto_cancel_hours")
    op.drop_column("spaces", "auto_cancel_enabled")
    op.drop_column("spaces", "payment_methods")
    op.drop_column("spaces", "payment_flow")
