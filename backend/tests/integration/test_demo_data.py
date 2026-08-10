"""Smoke test for the --demo dataset generators.

Exercises the net-new demo generators (members, billing, SEPA, reminders)
against a minimal base install and asserts the acceptance criteria: members
across all statuses, receipts across every state, at least one mandate and one
reminder, and idempotence on re-run.
"""

from app.cli import demo_data
from app.cli.seed import (
    seed_address_types,
    seed_contact_types,
    seed_demo_org_settings,
    seed_groups,
    seed_membership_types,
)
from app.domains.billing.models import Receipt, SepaMandate
from app.domains.members.models import Member
from app.domains.reminders.models import Reminder

ALL_MEMBER_STATUSES = {"active", "pending", "suspended", "expired", "cancelled"}
ALL_RECEIPT_STATUSES = {"paid", "emitted", "pending", "overdue", "returned", "cancelled", "new"}


def _base_install(db):
    seed_address_types(db)
    seed_contact_types(db)
    seed_demo_org_settings(db)
    groups = seed_groups(db)
    return seed_membership_types(db, groups)


def _run_generators(db, membership_type):
    demo_data.generate_members(db, membership_type)
    demo_data.generate_billing(db, created_by=None)
    demo_data.generate_sepa(db)
    demo_data.generate_reminders(db, created_by=None)


class TestDemoDataset:
    def test_demo_dataset_covers_all_states(self, db):
        membership_type = _base_install(db)
        _run_generators(db, membership_type)

        # Members across all statuses, with join dates spread across the year.
        member_statuses = {
            s for (s,) in db.query(Member.status).distinct().all()
        }
        assert ALL_MEMBER_STATUSES.issubset(member_statuses)
        join_months = {
            m.joined_at.month
            for m in db.query(Member).filter(Member.joined_at.isnot(None)).all()
        }
        assert len(join_months) >= 3  # spread, not all on one date

        # Receipts across every state.
        receipt_statuses = {
            s for (s,) in db.query(Receipt.status)
            .filter(Receipt.receipt_number.like("DEMO-%")).distinct().all()
        }
        assert ALL_RECEIPT_STATUSES.issubset(receipt_statuses)

        # Paid receipts carry a payment date → revenue; unpaid an emission date.
        paid = db.query(Receipt).filter(
            Receipt.receipt_number.like("DEMO-%"), Receipt.status == "paid"
        ).all()
        assert paid and all(r.payment_date is not None for r in paid)

        # At least one mandate and one reminder.
        assert db.query(SepaMandate).count() >= 1
        assert db.query(Reminder).count() >= 1

    def test_demo_dataset_is_idempotent(self, db):
        membership_type = _base_install(db)
        _run_generators(db, membership_type)

        before = (
            db.query(Member).count(),
            db.query(Receipt).filter(Receipt.receipt_number.like("DEMO-%")).count(),
            db.query(SepaMandate).count(),
            db.query(Reminder).count(),
        )
        assert all(c > 0 for c in before)

        # Re-run: every generator early-returns, nothing is added.
        _run_generators(db, membership_type)

        after = (
            db.query(Member).count(),
            db.query(Receipt).filter(Receipt.receipt_number.like("DEMO-%")).count(),
            db.query(SepaMandate).count(),
            db.query(Reminder).count(),
        )
        assert before == after
