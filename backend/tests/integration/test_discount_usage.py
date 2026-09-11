"""Discount usage is decided under a lock and released on cancellation.

``current_uses`` is a cached counter incremented in Python. Without a row lock
two redemptions arriving together both read ``max_uses - 1``, both pass the
check and both increment, so a code capped at N is redeemed N + 1 times. And a
use taken by a registration that is later cancelled must go back, or the code
burns a slot nobody used.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from itertools import count

import pytest
from sqlalchemy import event

from app.domains.activities.discount_service import (
    DiscountError,
    validate_discount_code,
)
from app.domains.activities.models import Activity, ActivityPrice, DiscountCode
from app.domains.activities.registration_service import (
    RegistrationError,
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
        org = OrganizationSettings(id=1, name="Discount Club", default_vat_rate=21)
        db.add(org)
        db.flush()
    return org


@pytest.fixture
def membership_type(db):
    mt = MembershipType(name="Discount", slug=f"discount-{next(_seq)}", is_active=True)
    db.add(mt)
    db.flush()
    return mt


def _member(db, membership_type, suffix):
    person = Person(
        first_name="Disc", last_name=suffix, email=f"disc-{suffix}@example7a1c4.com"
    )
    db.add(person)
    db.flush()
    member = Member(
        person_id=person.id,
        membership_type_id=membership_type.id,
        member_number=f"DISC-{suffix}",
        status="active",
    )
    db.add(member)
    db.flush()
    return member


def _activity(db, *, code="SAVE", max_uses=1):
    now = datetime.now(timezone.utc)
    activity = Activity(
        name="Discount Activity",
        slug=f"discount-activity-{next(_seq)}",
        starts_at=now + timedelta(days=10),
        ends_at=now + timedelta(days=11),
        registration_starts_at=now - timedelta(days=1),
        registration_ends_at=now + timedelta(days=9),
        max_participants=50,
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
    discount = DiscountCode(
        activity_id=activity.id,
        code=code,
        discount_type="percentage",
        discount_value=Decimal("10"),
        max_uses=max_uses,
        current_uses=0,
        is_active=True,
    )
    db.add_all([price, discount])
    db.flush()
    return activity, price, discount


def _statements(db, fn):
    seen = []

    def record(conn, cursor, statement, params, context, executemany):
        seen.append(" ".join(statement.split()))

    event.listen(db.get_bind(), "before_cursor_execute", record)
    try:
        fn()
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", record)
    return seen


class TestUsageIsLocked:
    """Asserts the lock is requested, not that two connections contend — the
    ``db`` fixture is one rolled-back transaction, and a test that blocks on a
    lock is the kind that turns flaky in parallel (see issue #58)."""

    def test_redemption_locks_the_code_row(self, db, org, membership_type):
        activity, price, _ = _activity(db)
        member = _member(db, membership_type, "lock")

        seen = _statements(
            db,
            lambda: register_member(db, activity, member, price.id, discount_code="SAVE"),
        )
        locks = [s for s in seen if "discount_codes" in s and "FOR UPDATE" in s]
        assert locks, "register_member must SELECT ... FOR UPDATE the discount row"

    def test_preview_does_not_lock(self, db, org, membership_type):
        activity, _, _ = _activity(db)

        seen = _statements(
            db, lambda: validate_discount_code(db, activity.id, "SAVE")
        )
        assert not [s for s in seen if "discount_codes" in s and "FOR UPDATE" in s]

    def test_cap_is_read_through_the_lock(self, db, org, membership_type):
        """A stale in-session counter must not let a redemption past the cap."""
        activity, price, discount = _activity(db, max_uses=1)
        first = _member(db, membership_type, "stale1")
        second = _member(db, membership_type, "stale2")

        register_member(db, activity, first, price.id, discount_code="SAVE")
        # Simulate another transaction having spent the last use.
        db.execute(
            DiscountCode.__table__.update()
            .where(DiscountCode.id == discount.id)
            .values(current_uses=1)
        )
        discount.current_uses = 0  # stale in-session value

        with pytest.raises(RegistrationError, match="maximum uses"):
            register_member(db, activity, second, price.id, discount_code="SAVE")


class TestUsageIsReleased:
    def test_cancelling_gives_the_use_back(self, db, org, membership_type):
        activity, price, discount = _activity(db, max_uses=1)
        first = _member(db, membership_type, "rel1")
        second = _member(db, membership_type, "rel2")

        reg = register_member(db, activity, first, price.id, discount_code="SAVE")
        assert discount.current_uses == 1
        with pytest.raises(DiscountError, match="maximum uses"):
            validate_discount_code(db, activity.id, "SAVE")

        cancel_registration(db, reg)
        db.flush()
        db.refresh(discount)
        assert discount.current_uses == 0

        register_member(db, activity, second, price.id, discount_code="SAVE")
        db.flush()
        db.refresh(discount)
        assert discount.current_uses == 1

    def test_release_never_goes_below_zero(self, db, org, membership_type):
        activity, price, discount = _activity(db, max_uses=5)
        member = _member(db, membership_type, "floor")
        reg = register_member(db, activity, member, price.id, discount_code="SAVE")
        discount.current_uses = 0  # counter already drifted low
        db.flush()

        cancel_registration(db, reg)
        db.flush()
        db.refresh(discount)
        assert discount.current_uses == 0

    def test_cancelling_without_a_code_touches_nothing(self, db, org, membership_type):
        activity, price, discount = _activity(db, max_uses=5)
        member = _member(db, membership_type, "none")
        reg = register_member(db, activity, member, price.id)

        cancel_registration(db, reg)
        db.flush()
        db.refresh(discount)
        assert discount.current_uses == 0
