"""The scheduled sweep of accounts nobody ever confirmed (#645).

Hygiene rather than a fix: #644 frees an address the moment somebody with a
better claim arrives, and this clears the ones nobody comes back for. A sweep
leaves a window between runs, so it does not replace that.

The dangerous half is the scope. Verification state lives only on an account, so
a sweep written over persons or members would match every member an
administrator ever entered by hand and delete the club. The tests below pin the
query to ``users`` rows, pin the grace period, and pin the fact that the task is
actually registered with Celery, which a beat entry alone does not guarantee.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.security.password import hash_password
from app.domains.audit.models import AuditLog
from app.domains.auth.cleanup_service import (
    UNVERIFIED_GRACE_DAYS,
    purge_unverified_accounts,
)
from app.domains.auth.models import User
from app.domains.members.models import Member, MembershipType
from app.domains.members.service import create_member
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Party, Person


@pytest.fixture
def org(db):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(
            id=1, name="Test Club", locale="es", timezone="Europe/Madrid",
            currency="EUR", date_format="DD/MM/YYYY",
        )
        db.add(org)
    db.flush()
    return org


@pytest.fixture
def membership_type(db):
    mt = MembershipType(
        name="Sweep Standard", slug="sweep-standard", base_price=0,
        billing_frequency="annual",
    )
    db.add(mt)
    db.flush()
    return mt


def _account(db, membership_type, email, *, verified, age_days):
    person = Person(first_name="Sweep", last_name="Target", email=email)
    db.add(person)
    db.flush()
    user = User(
        party_id=person.party_id, email=email,
        password_hash=hash_password("password123"), role="member",
        is_active=True, email_verified=verified,
    )
    db.add(user)
    db.flush()
    member = Member(
        party_id=person.party_id, membership_type_id=membership_type.id,
        member_number=None, status="pending",
    )
    db.add(member)
    db.flush()
    # created_at has a server default, so age is set after the insert.
    user.created_at = datetime.now(timezone.utc) - timedelta(days=age_days)
    db.flush()
    return user, member


class TestWhatTheSweepTakes:
    def test_it_deletes_an_account_left_unconfirmed_past_the_grace_period(
        self, db, org, membership_type
    ):
        user, member = _account(
            db, membership_type, "sweep-old@example.com",
            verified=False, age_days=UNVERIFIED_GRACE_DAYS + 1,
        )
        party_id, member_id = user.party_id, member.id

        summary = purge_unverified_accounts(db)

        assert summary["deleted"] == 1
        # The party goes, so nothing is orphaned and the address is free.
        assert db.query(Party).filter(Party.id == party_id).first() is None
        assert db.query(Member).filter(Member.id == member_id).first() is None
        assert db.query(User).filter(User.email == "sweep-old@example.com").count() == 0

    def test_it_logs_the_deletion_to_the_audit_trail(
        self, db, org, membership_type
    ):
        user, _ = _account(
            db, membership_type, "sweep-audit@example.com",
            verified=False, age_days=UNVERIFIED_GRACE_DAYS + 1,
        )
        party_id = user.party_id

        purge_unverified_accounts(db)

        entry = (
            db.query(AuditLog)
            .filter(
                AuditLog.table_name == "party",
                AuditLog.record_id == party_id,
                AuditLog.action == "delete",
            )
            .first()
        )
        assert entry is not None, "a scheduled cascade must leave a trace"


class TestWhatTheSweepLeavesAlone:
    def test_it_spares_an_account_still_inside_the_grace_period(
        self, db, org, membership_type
    ):
        user, _ = _account(
            db, membership_type, "sweep-young@example.com",
            verified=False, age_days=UNVERIFIED_GRACE_DAYS - 1,
        )
        party_id = user.party_id

        summary = purge_unverified_accounts(db)

        assert summary["deleted"] == 0
        assert db.query(Party).filter(Party.id == party_id).first() is not None

    def test_it_spares_a_verified_account_however_old(
        self, db, org, membership_type
    ):
        user, _ = _account(
            db, membership_type, "sweep-verified@example.com",
            verified=True, age_days=UNVERIFIED_GRACE_DAYS * 10,
        )
        party_id = user.party_id

        summary = purge_unverified_accounts(db)

        assert summary["deleted"] == 0
        assert db.query(Party).filter(Party.id == party_id).first() is not None

    def test_it_spares_every_member_an_admin_created_by_hand(
        self, db, org, membership_type
    ):
        """The one that matters. These have no account, so no verification state.

        A sweep written over persons or members rather than ``users`` rows would
        match all of them, and an established club is mostly made of them.
        """
        member = create_member(
            db, first_name="Walk", last_name="In",
            email="sweep-walkin@example.com",
            membership_type_id=membership_type.id,
        )
        db.flush()
        party_id = member.party_id
        assert member.user is None

        summary = purge_unverified_accounts(db)

        assert summary["deleted"] == 0
        assert db.query(Party).filter(Party.id == party_id).first() is not None
        assert db.query(Member).filter(Member.id == member.id).first() is not None


class TestTheTaskIsActuallyWired:
    def test_every_beat_entry_points_at_a_task_the_worker_will_have(self):
        """A beat entry naming a module absent from ``include`` fires nothing.

        The schedule and the ``include`` list are edited in different places and
        nothing tied them together, so a new entry could name a task the worker
        never imports and the only symptom would be a job that silently never
        runs.

        ``import_default_modules`` is what the worker itself calls on startup:
        task registration is lazy, so before it every one of these is absent,
        mine and the four that predate it alike. Asserting over the whole
        schedule rather than one entry, because the next person to add one gets
        the check for free.
        """
        from app.core.celery_app import celery

        celery.loader.import_default_modules()

        missing = [
            f"{name} -> {entry['task']}"
            for name, entry in celery.conf.beat_schedule.items()
            if entry["task"] not in celery.tasks
        ]
        assert not missing, f"beat entries with no registered task: {missing}"
        assert (
            "scheduled-unverified-cleanup" in celery.conf.beat_schedule
        ), "the sweep must be scheduled, not merely importable"
