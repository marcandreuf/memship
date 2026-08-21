"""Capacity must be decided under a lock, and only for the seat that was freed.

``current_participants`` is a cached column incremented in Python. Without a row
lock two registrations arriving together both read ``max - 1``, both confirm and
both increment, so the activity goes over capacity and the counter drifts from
the ``registrations`` rows. Waitlist promotion had the mirror problem: it filled
a seat without checking there was one, and could fill it from another modality.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from itertools import count

import pytest
from sqlalchemy import event

from app.domains.activities.models import Activity, ActivityModality, ActivityPrice
from app.domains.activities.registration_service import (
    cancel_registration,
    register_member,
)
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person

PRICE = Decimal("10.00")
_slugs = count(1)


@pytest.fixture
def org(db):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(id=1, name="Capacity Club", default_vat_rate=21)
        db.add(org)
        db.flush()
    return org


@pytest.fixture
def membership_type(db):
    mt = MembershipType(name="Capacity", slug="capacity", is_active=True)
    db.add(mt)
    db.flush()
    return mt


def _member(db, membership_type, suffix):
    person = Person(
        first_name="Cap", last_name=suffix, email=f"cap-{suffix}@examplee6e3b1.com"
    )
    db.add(person)
    db.flush()
    member = Member(
        person_id=person.id,
        membership_type_id=membership_type.id,
        member_number=f"CAP-{suffix}",
        status="active",
    )
    db.add(member)
    db.flush()
    return member


def _activity(db, *, max_participants=1, waiting_list=True):
    now = datetime.now(timezone.utc)
    activity = Activity(
        name="Capacity Activity",
        slug=f"capacity-activity-{next(_slugs)}",
        starts_at=now + timedelta(days=10),
        ends_at=now + timedelta(days=11),
        registration_starts_at=now - timedelta(days=1),
        registration_ends_at=now + timedelta(days=9),
        max_participants=max_participants,
        status="published",
        is_active=True,
        features={"waiting_list": waiting_list},
    )
    db.add(activity)
    db.flush()
    price = ActivityPrice(
        activity_id=activity.id,
        name="Standard",
        amount=PRICE,
        is_default=True,
        is_active=True,
    )
    db.add(price)
    db.flush()
    return activity, price


def _modality(db, activity, name, max_participants):
    m = ActivityModality(
        activity_id=activity.id,
        name=name,
        max_participants=max_participants,
        current_participants=0,
        is_active=True,
    )
    db.add(m)
    db.flush()
    return m


class TestCapacityIsLocked:
    """The capacity read must take a row lock before deciding.

    This asserts the statement is emitted, not that two connections actually
    contend. The `db` fixture is one connection inside a transaction that is
    rolled back, so a real race would need committed setup on a second
    connection, and a test that deliberately blocks on a lock is exactly the
    kind that turns flaky under parallel load (see issue #58). What can go wrong
    silently is the lock not being requested at all, which is what this catches.
    """

    def _statements(self, db, fn):
        seen = []

        def record(conn, cursor, statement, params, context, executemany):
            seen.append(" ".join(statement.split()))

        event.listen(db.get_bind(), "before_cursor_execute", record)
        try:
            fn()
        finally:
            event.remove(db.get_bind(), "before_cursor_execute", record)
        return seen

    def test_activity_row_is_locked(self, db, org, membership_type):
        activity, price = _activity(db, max_participants=2)
        member = _member(db, membership_type, "locked")

        sql = self._statements(
            db, lambda: register_member(db, activity, member, price.id)
        )
        locks = [s for s in sql if "FOR UPDATE" in s.upper() and "activities" in s]
        assert locks, "register_member must SELECT ... FOR UPDATE the activity row"

    def test_modality_row_is_locked_too(self, db, org, membership_type):
        activity, price = _activity(db, max_participants=5)
        modality = _modality(db, activity, "Morning", max_participants=2)
        member = _member(db, membership_type, "lockedmod")

        sql = self._statements(
            db,
            lambda: register_member(
                db, activity, member, price.id, modality_id=modality.id
            ),
        )
        locks = [
            s for s in sql if "FOR UPDATE" in s.upper() and "activity_modalities" in s
        ]
        assert locks, "the modality row must be locked when one is supplied"

    def test_the_lock_refreshes_the_counter(self, db, org, membership_type):
        """populate_existing() is what makes the lock worth taking.

        Without it SQLAlchemy returns the identity-mapped instance and the stale
        counter is read straight through the lock.
        """
        activity, price = _activity(db, max_participants=1)
        first = _member(db, membership_type, "stale1")
        second = _member(db, membership_type, "stale2")

        register_member(db, activity, first, price.id)
        # Simulate another transaction having taken the seat.
        db.execute(
            Activity.__table__.update()
            .where(Activity.id == activity.id)
            .values(current_participants=1)
        )
        activity.current_participants = 0  # stale in-session value

        second_reg = register_member(db, activity, second, price.id)
        assert second_reg.status == "waitlist"


class TestPromotionRespectsCapacity:
    def test_no_promotion_when_the_cap_was_lowered(self, db, org, membership_type):
        """A freed seat is not proof there is room."""
        activity, price = _activity(db, max_participants=2)
        first = _member(db, membership_type, "cap1")
        second = _member(db, membership_type, "cap2")
        third = _member(db, membership_type, "cap3")

        a = register_member(db, activity, first, price.id)
        register_member(db, activity, second, price.id)
        waiting = register_member(db, activity, third, price.id)
        assert waiting.status == "waitlist"

        # An admin shrinks the activity while someone is waiting.
        activity.max_participants = 1
        db.flush()

        cancel_registration(db, a)

        assert waiting.status == "waitlist", "promoted past the lowered cap"


class TestPromotionStaysInItsModality:
    def test_a_freed_unmodalitied_seat_does_not_promote_across(
        self, db, org, membership_type
    ):
        """The bug: modality_id None meant an unfiltered query.

        Cancelling a registration that had no modality promoted the oldest
        waitlister in the whole activity — possibly one waiting on a different
        modality that is still full — and incremented that modality past its cap.
        """
        activity, price = _activity(db, max_participants=2)
        morning = _modality(db, activity, "Morning", max_participants=1)

        plain = _member(db, membership_type, "plain")
        morning_taken = _member(db, membership_type, "mtaken")
        morning_waiting = _member(db, membership_type, "mwait")

        plain_reg = register_member(db, activity, plain, price.id)
        register_member(db, activity, morning_taken, price.id, modality_id=morning.id)
        waiting = register_member(
            db, activity, morning_waiting, price.id, modality_id=morning.id
        )
        assert waiting.status == "waitlist"

        cancel_registration(db, plain_reg)

        assert waiting.status == "waitlist", "promoted into a full modality"
        assert morning.current_participants == 1
