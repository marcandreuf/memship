"""Registration emails go out after the commit, never before.

The service functions used to call ``.delay()`` directly, so the Celery worker
could run before the endpoint's ``db.commit()`` — or after a commit that
failed. Now they queue the dispatch on the session and it fires from the
``after_commit`` event, with a rollback discarding it.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from itertools import count
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.db.after_commit import run_after_commit
from app.domains.activities.models import Activity, ActivityPrice
from app.domains.activities.registration_service import (
    cancel_registration,
    register_member,
)
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person

_seq = count(1)


@pytest.fixture
def org(db):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(id=1, name="Email Club", default_vat_rate=21)
        db.add(org)
        db.flush()
    return org


@pytest.fixture
def membership_type(db):
    mt = MembershipType(name="Emails", slug=f"emails-{next(_seq)}", is_active=True)
    db.add(mt)
    db.flush()
    return mt


def _member(db, membership_type, suffix):
    person = Person(
        first_name="Mail", last_name=suffix, email=f"mail-{suffix}@example9f2c1.com"
    )
    db.add(person)
    db.flush()
    member = Member(
        person_id=person.id,
        membership_type_id=membership_type.id,
        member_number=f"MAIL-{suffix}",
        status="active",
    )
    db.add(member)
    db.flush()
    return member


def _activity(db, *, max_participants=1):
    now = datetime.now(timezone.utc)
    activity = Activity(
        name="Email Activity",
        slug=f"email-activity-{next(_seq)}",
        starts_at=now + timedelta(days=10),
        ends_at=now + timedelta(days=11),
        registration_starts_at=now - timedelta(days=1),
        registration_ends_at=now + timedelta(days=9),
        max_participants=max_participants,
        status="published",
        is_active=True,
        features={"waiting_list": True},
    )
    db.add(activity)
    db.flush()
    price = ActivityPrice(
        activity_id=activity.id,
        name="Standard",
        amount=Decimal("10.00"),
        is_default=True,
        is_active=True,
    )
    db.add(price)
    db.flush()
    return activity, price


class TestRunAfterCommit:
    def test_runs_only_once_the_session_commits(self, db):
        calls = []
        run_after_commit(db, lambda: calls.append("a"))
        run_after_commit(db, lambda: calls.append("b"))
        assert calls == []

        db.commit()
        assert calls == ["a", "b"]

        # The queue is drained: a later commit does not replay it.
        db.commit()
        assert calls == ["a", "b"]

    def test_one_failing_hook_does_not_block_the_others(self, db):
        calls = []

        def boom():
            raise RuntimeError("smtp down")

        run_after_commit(db, boom)
        run_after_commit(db, lambda: calls.append("after"))
        db.commit()
        assert calls == ["after"]

    def test_rollback_discards_the_queue(self, db):
        calls = []
        db.execute(text("SELECT 1"))  # autobegin, as any request would have
        run_after_commit(db, lambda: calls.append("never"))
        db.rollback()
        db.commit()
        assert calls == []

    def test_nested_savepoint_rollback_keeps_the_queue(self, db):
        calls = []
        run_after_commit(db, lambda: calls.append("kept"))
        try:
            with db.begin_nested():
                raise RuntimeError("receipt failed")
        except RuntimeError:
            pass
        db.commit()
        assert calls == ["kept"]


class TestRegistrationEmailsWaitForCommit:
    def test_confirmation_is_queued_until_commit(self, db, org, membership_type):
        activity, price = _activity(db)
        member = _member(db, membership_type, "confirm")

        with patch(
            "app.tasks.email_tasks.send_registration_email_task.delay"
        ) as delay:
            registration = register_member(db, activity, member, price.id)
            assert registration.status == "confirmed"
            delay.assert_not_called()

            db.commit()

        delay.assert_called_once()
        kwargs = delay.call_args.kwargs
        assert kwargs["to"] == "mail-confirm@example9f2c1.com"
        assert kwargs["status"] == "confirmed"
        assert kwargs["activity_name"] == "Email Activity"

    def test_cancellation_and_promotion_are_queued_until_commit(
        self, db, org, membership_type
    ):
        activity, price = _activity(db, max_participants=1)
        first = _member(db, membership_type, "first")
        second = _member(db, membership_type, "second")

        with patch("app.tasks.email_tasks.send_registration_email_task.delay"):
            held = register_member(db, activity, first, price.id)
            waiting = register_member(db, activity, second, price.id)
            db.commit()
        assert held.status == "confirmed"
        assert waiting.status == "waitlist"

        with (
            patch(
                "app.tasks.email_tasks.send_cancellation_email_task.delay"
            ) as cancel_delay,
            patch(
                "app.tasks.email_tasks.send_promotion_email_task.delay"
            ) as promote_delay,
        ):
            cancel_registration(db, held)
            assert waiting.status == "confirmed"
            cancel_delay.assert_not_called()
            promote_delay.assert_not_called()

            db.commit()

        cancel_delay.assert_called_once()
        assert cancel_delay.call_args.kwargs["to"] == "mail-first@example9f2c1.com"
        promote_delay.assert_called_once()
        assert promote_delay.call_args.kwargs["to"] == "mail-second@example9f2c1.com"

    def test_rolled_back_registration_sends_nothing(self, db, org, membership_type):
        activity, price = _activity(db)
        member = _member(db, membership_type, "rollback")

        with patch(
            "app.tasks.email_tasks.send_registration_email_task.delay"
        ) as delay:
            register_member(db, activity, member, price.id)
            db.rollback()
            db.commit()

        delay.assert_not_called()
