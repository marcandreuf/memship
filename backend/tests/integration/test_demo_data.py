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
from app.domains.organizations.models import OrganizationSettings
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


# Every key the application reads out of ``organization_settings.features``,
# gathered from the readers rather than from any one writer: the frontend's
# settings forms and route gates, and the backend's billing, reminder, lapse,
# booking and registration services. `waiting_list` is NOT one of them — that
# key lives on ``activities.features``, a different column that happens to share
# the name (#317).
ALL_FEATURE_FLAGS = {
    "billing_notification_email",
    "booking_cancellation_deadline_hours",
    "booking_waitlist_enabled",
    "booking_window_days",
    "bookings",
    "communications",
    "custom_profile_fields",
    "custom_roles",
    "gender_options",
    "member_card",
    "membership_fee_due_days",
    "membership_lapse_enabled",
    "membership_lapse_grace_days",
    "payment_reminders_enabled",
    "public_registration",
    "recurring_billing_day",
    "recurring_billing_enabled",
    "registration_requires_approval",
    "reminder_days_after_due",
    "reminder_max_count",
    "reminder_repeat_days",
}

# What a real first install starts with, and it is meant to be this short: a club
# opts into each module deliberately. Documented in
# docs/self-hosting/feature-flags.md.
FRESH_INSTALL_FLAGS = {"custom_roles", "gender_options"}


def _features(db) -> dict:
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    return dict(org.features or {})


class TestFeatureFlagSeeding:
    """#317: nineteen of the twenty-one flags were absent on every seeded instance.

    The fresh-install half of that is intended and stays; what these pin is that
    it stays *deliberate* — a flag added to the base install trips the first
    test, and a flag the demo forgets trips the second.
    """

    def test_a_fresh_install_switches_on_only_what_it_means_to(self, db):
        _base_install(db)
        assert set(_features(db)) == FRESH_INSTALL_FLAGS

    def test_the_demo_path_configures_every_flag(self, db):
        _base_install(db)
        demo_data.seed_demo_features(db)

        present = set(_features(db))
        assert ALL_FEATURE_FLAGS - present == set(), "a flag the demo never sets"
        assert present - ALL_FEATURE_FLAGS == set(), "a flag nothing reads"

    def test_the_demo_numerics_match_the_defaults_the_code_falls_back_to(self, db):
        """Otherwise the Settings form shows one set of numbers and an unconfigured
        instance runs on another."""
        from app.domains.billing.lapse_service import DEFAULT_GRACE_DAYS
        from app.domains.billing.recurring_billing_service import (
            DEFAULT_MEMBERSHIP_FEE_DUE_DAYS,
        )

        _base_install(db)
        demo_data.seed_demo_features(db)
        f = _features(db)

        assert f["membership_lapse_grace_days"] == DEFAULT_GRACE_DAYS
        assert f["membership_fee_due_days"] == DEFAULT_MEMBERSHIP_FEE_DUE_DAYS
        assert (f["reminder_days_after_due"], f["reminder_repeat_days"], f["reminder_max_count"]) == (3, 7, 3)
        assert (f["booking_window_days"], f["booking_cancellation_deadline_hours"]) == (14, 24)

    def test_seeding_features_leaves_flags_it_does_not_name_alone(self, db):
        """`custom_roles` and `gender_options` come from the base install, and a
        later release adding a key must not be silently dropped on a re-seed."""
        _base_install(db)
        org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
        org.features = {**org.features, "something_a_later_release_added": "kept"}
        db.flush()

        demo_data.seed_demo_features(db)
        f = _features(db)

        assert f["something_a_later_release_added"] == "kept"
        assert f["custom_roles"] is True
        assert len(f["gender_options"]) == 5

    def test_the_demo_entry_point_reaches_the_feature_seeder(self, db):
        """Wiring, not behaviour.

        Every other test here calls a generator directly, so a `seed_demo_data`
        that never called `seed_demo_features` would leave them all green and
        `--demo` still producing the two-flag instance #317 is about.
        """
        membership_type = _base_install(db)
        demo_data.seed_demo_data(db, membership_type, created_by=None)
        assert set(_features(db)) == ALL_FEATURE_FLAGS

    def test_two_flags_are_on_while_absent(self, db):
        """#317 read the nineteen absent flags as nineteen modules switched off.

        Two of them are not. `get_registration_settings` reads both with a `True`
        default, so a fresh install accepts public sign-ups and holds them for
        approval — documented in docs/self-hosting/feature-flags.md, pinned here
        because the doc is only as good as the default it describes.
        """
        from app.domains.auth.service import get_registration_settings

        _base_install(db)
        absent = _features(db)
        assert "public_registration" not in absent
        assert "registration_requires_approval" not in absent
        assert get_registration_settings(db) == (True, True)

    def test_seeding_features_twice_changes_nothing(self, db):
        _base_install(db)
        demo_data.seed_demo_features(db)
        once = _features(db)
        demo_data.seed_demo_features(db)
        assert _features(db) == once
