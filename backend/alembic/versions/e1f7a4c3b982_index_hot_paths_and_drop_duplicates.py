"""Index the hot paths, and drop the indexes that only cost writes

Revision ID: e1f7a4c3b982
Revises: 9e4b7c2d1a63
Create Date: 2026-11-24

Step 2 of #459. Step 1 (`54ad095`) rewrote the queries; without the indexes here
two of those rewrites cannot pay, and without the rewrites two of these indexes
cannot be used.

Measured as a controlled A/B on 5,000 members and 50,000 receipts from
``seed.py --volume 5000``: same statistics, same cache, same session, flipping
only ``pg_index.indisvalid`` on the thirteen indexes below. The volume seeder
writes neither billing periods nor a dunning backlog, so those two were given
realistic data in the same rolled-back transaction; without that the last two
rows measure nothing.

=========================  ==================  =================
Query                      With these indexes  Without
=========================  ==================  =================
Revenue chart              6.3 ms / 1591 buf   15.6 ms, seq scan
Remittance detail          0.4 ms / 97 buf     8.6 ms, seq scan
Receipts search            2.4 ms / 408 buf    59.7 ms, seq scan
Billing run anti-join      12.8 ms / 14298     26.5 ms / 21253
mark_overdue sweep         1.8 ms / 896 buf    2.6 ms / 988 buf
Outstanding                7.4 ms / 2074       7.9 ms / 2074
Members list, two words    17.9 ms / 508       16.1 ms / 508
=========================  ==================  =================

The last two rows are the ones that decided what this revision does *not*
contain. Outstanding is already fixed by step 1's range predicate and gains
nothing further here. The members list is identical in both directions, which is
why four of §4's six trigram indexes are left out (below).

The revenue chart shows the coupling with step 1. With
``ix_receipts_status_payment_date`` present but the old ``extract('year', …)``
predicate still in place, the planner **still sequentially scans**: the index is
dead weight without step 1, and step 1 leaves the query scanning without the
index. Neither half stands up alone.

The three notification and announcement_recipients indexes are reasoned rather
than measured. Those tables hold 40 rows in the volume dataset because the
seeder writes no announcements, and Postgres sequentially scans 40 rows whatever
exists. They index a foreign key used by ``ON DELETE CASCADE`` and the two
columns the "Seen" badge looks up, on tables that grow as members x
announcements.

Everything is built and dropped ``CONCURRENTLY`` inside
``op.get_context().autocommit_block()``. There is one deployed instance, it is
production, and the API container runs ``alembic upgrade head`` on start, so a
plain ``CREATE INDEX`` would hold ACCESS EXCLUSIVE on ``receipts`` for the
duration of a deploy. The cost of ``CONCURRENTLY`` is that it cannot run in a
transaction, so this revision is **not atomic**: see "If this revision fails"
below.

Creates run before drops, which is load-bearing twice over.
``ix_notifications_user_unread`` is replaced by a narrower partial index, and
``ix_announcement_recipients_announcement`` becomes a prefix of a new composite.
Dropping either before its replacement exists would leave the hot path
unindexed in between.

What this deliberately leaves out, with the reason, so it is not read as an
oversight:

- **Four of §4's six trigram indexes.** §4 proposes them for ``persons``
  (``first_name``, ``last_name``, ``email``) and ``members.member_number``, and
  asserts the planner will use them for ``ILIKE`` with no query change. That is
  true for the receipts search and false for the members list.
  ``core/search.py:match_words`` ORs each typed word across four columns
  spanning three tables, and ``build_members_query`` joins ``members`` to
  ``persons`` to ``party`` to supply them, so no single-table index can be
  reached below the join. Measured twice, two different ways: with all four
  actually built, 14.8 ms and 481 buffers, identical to without them; and in
  the A/B above, where the members list is the one row that does not move.
  Four GIN indexes slowing every member write for nothing. (§4's
  ``persons.email`` is also stale; ``email`` lives on ``party``.)
- **The ~8 ``created_by`` / ``cancelled_by`` / ``assigned_by`` indexes.** §3
  rates them low priority itself. They serve ``ON DELETE SET NULL`` when a user
  is deleted, which is rare, against a write cost on every row of eight tables.

Both exclusions follow ADR 0007: at most about 10,000 members per install, so an
index is justified by what it buys at that volume and not by what it would buy
above it.

``ix_persons_stripe_customer_id`` is **not** on the drop list and must not be
added to it. The model declares ``unique=True, index=True``, which looks like
two indexes but emits one: that index is ``indisunique`` and is the mechanism
enforcing uniqueness on the column.

If this revision fails: a ``CONCURRENTLY`` build that is interrupted leaves an
``INVALID`` index behind, and re-running this revision will **not** repair it,
because ``IF NOT EXISTS`` sees the name and skips. Find them with
``SELECT i.relname FROM pg_index x JOIN pg_class i ON i.oid = x.indexrelid
WHERE NOT x.indisvalid``, drop each one, and run the upgrade again.

The downgrade restores every dropped index and removes every added one. It does
not drop the ``pg_trgm`` extension: ``DROP EXTENSION`` would cascade to anything
else that comes to depend on it, and leaving an unused extension installed costs
nothing.
"""

from alembic import op

revision = "e1f7a4c3b982"
down_revision = "9e4b7c2d1a63"
branch_labels = None
depends_on = None


# (name, table, definition) — the definition is everything after ``ON <table>``.
# Built in this order; the last two need ``pg_trgm``.
ADDED = [
    # §3: foreign keys and lookup columns with no index, each confirmed absent
    # against pg_index rather than against the models.
    (
        "ix_receipts_remittance_id",
        "receipts",
        "(remittance_id)",
    ),
    (
        "ix_receipts_registration_id",
        "receipts",
        "(registration_id)",
    ),
    (
        "ix_receipts_concept_id",
        "receipts",
        "(concept_id)",
    ),
    (
        "ix_members_guardian_party_id",
        "members",
        "(guardian_party_id)",
    ),
    (
        "ix_announcement_recipients_member_id",
        "announcement_recipients",
        "(member_id)",
    ),
    # The "Seen" badge: communications/service.py joins notifications on
    # (user_id, source_type, source_id) per announcement viewed. This also
    # carries the read_at IS NOT NULL count, which is why dropping
    # ix_notifications_user_unread below does not leave that path unindexed.
    (
        "ix_notifications_source",
        "notifications",
        "(source_type, source_id)",
    ),
    # The announcement fan-out writes one row per member and then reads them
    # back by announcement. Non-unique deliberately: (announcement_id,
    # member_id) is a natural unique key, but a UNIQUE build that met a
    # duplicate would leave an INVALID index behind on a production deploy. The
    # constraint belongs in its own revision, after a check that the data
    # permits it.
    (
        "ix_announcement_recipients_ann_member",
        "announcement_recipients",
        "(announcement_id, member_id)",
    ),
    # §2: the billing-run anti-join from step 1 probes this once per member.
    # Column order follows its equality predicates; is_active and
    # status != 'cancelled' are left to the recheck, which sees at most one row.
    (
        "ix_receipts_billing_period",
        "receipts",
        "(party_id, origin, billing_period_start, billing_period_end)",
    ),
    # §5: the revenue chart, bucketed by payment_date. Equality on status leads,
    # the range follows. This is the index the issue called optional; it is the
    # entire fix for that query, and payment_date had no index at all.
    (
        "ix_receipts_status_payment_date",
        "receipts",
        "(status, payment_date)",
    ),
    # mark_overdue (billing/reminder_service.py:40) scans for unpaid receipts
    # past due on every dunning run. The predicate matches its filters; origin
    # and document_type are left out so one index serves the whole pipeline.
    (
        "ix_receipts_open_due",
        "receipts",
        "(due_date) WHERE status IN ('pending', 'emitted') AND is_active"
        " AND payment_date IS NULL",
    ),
    # The unread badge, on every page load. Replaces the full
    # (user_id, read_at) index dropped below: every query on this path filters
    # read_at IS NULL (unread_count and mark_read), so the partial is both
    # smaller and sufficient.
    (
        "ix_notifications_unread",
        "notifications",
        "(user_id) WHERE read_at IS NULL",
    ),
    # §4, the two that measured: the receipts search, 53.4 ms to 1.6 ms.
    (
        "ix_receipts_receipt_number_trgm",
        "receipts",
        "USING gin (receipt_number gin_trgm_ops)",
    ),
    (
        "ix_receipts_description_trgm",
        "receipts",
        "USING gin (description gin_trgm_ops)",
    ),
]


# §6: every entry was confirmed present, non-unique and non-primary against
# pg_index, and confirmed to have another index covering its columns. Each
# definition here is the one being removed, so the downgrade restores it
# exactly.
DROPPED = [
    # index=True on an Integer primary key makes SQLAlchemy emit a second btree
    # beside the one the primary key already built. The one on receipts costs an
    # extra index write on every insert into the largest table.
    ("ix_receipts_id", "receipts", "(id)"),
    ("ix_concepts_id", "concepts", "(id)"),
    ("ix_remittances_id", "remittances", "(id)"),
    ("ix_remittance_receipts_id", "remittance_receipts", "(id)"),
    ("ix_sepa_mandates_id", "sepa_mandates", "(id)"),
    ("ix_webhook_events_id", "webhook_events", "(id)"),
    ("ix_billing_runs_id", "billing_runs", "(id)"),
    ("ix_receipt_reminders_id", "receipt_reminders", "(id)"),
    ("ix_payment_providers_id", "payment_providers", "(id)"),
    ("ix_reminders_id", "reminders", "(id)"),
    # Non-unique duplicates of a UNIQUE constraint's own index.
    ("idx_groups_slug", "groups", "(slug)"),
    ("idx_membership_types_slug", "membership_types", "(slug)"),
    ("idx_activities_slug", "activities", "(slug)"),
    ("idx_roles_slug", "roles", "(slug)"),
    (
        "idx_members_member_number",
        "members",
        "(member_number) WHERE member_number IS NOT NULL",
    ),
    # Leading column of a composite primary key, which already indexes it.
    ("idx_role_permissions_role", "role_permissions", "(role_id)"),
    ("idx_user_roles_user", "user_roles", "(user_id)"),
    # Leading column of uq_remittance_receipt.
    (
        "ix_remittance_receipts_remittance_id",
        "remittance_receipts",
        "(remittance_id)",
    ),
    # Replaced by ix_notifications_unread above.
    ("ix_notifications_user_unread", "notifications", "(user_id, read_at)"),
    # Now a prefix of ix_announcement_recipients_ann_member above.
    (
        "ix_announcement_recipients_announcement",
        "announcement_recipients",
        "(announcement_id)",
    ),
]


def _create(name: str, table: str, definition: str) -> None:
    op.execute(
        f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} ON {table} {definition}"
    )


def _drop(name: str) -> None:
    op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")


def upgrade() -> None:
    # Inside the transaction, so it is committed before the autocommit block the
    # trigram indexes are built in.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    with op.get_context().autocommit_block():
        for name, table, definition in ADDED:
            _create(name, table, definition)
        for name, _table, _definition in DROPPED:
            _drop(name)


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for name, table, definition in DROPPED:
            _create(name, table, definition)
        for name, _table, _definition in ADDED:
            _drop(name)
