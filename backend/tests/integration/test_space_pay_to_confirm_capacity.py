"""A pending booking holds its seat as surely as a booked one (#603).

Capacity is counted from the rows under a lock on the slot, so the risk the plan
names is a count that forgets ``pending``: overbooking, or a seat never freed.
These hold the counts to the rows through a booking's whole life, and that the
paths that decide capacity take the slot's lock.
"""

from datetime import timedelta

import pytest
from sqlalchemy import event, func

from app.domains.billing.service import mark_receipt_paid
from app.domains.bookings import service
from app.domains.bookings.models import Booking
from tests.integration.api.v1.test_redsys_flow import _create_redsys_provider
from tests.integration.test_bookings_service import _member, _org
from tests.integration.test_pay_to_confirm_payment import _stripe_provider
from tests.integration.test_receipt_payment import _auth_cookie, _create_admin
from tests.integration.test_space_pay_to_confirm_booking import _receipts, _slot, _space


def _assert_counts_match_rows(db, slot):
    db.flush()
    rows = dict(
        db.query(Booking.status, func.count())
        .filter(Booking.space_slot_id == slot.id)
        .group_by(Booking.status)
        .all()
    )
    held = rows.get("booked", 0) + rows.get("pending", 0)
    assert service._occupied(db, slot.id) == held
    assert held <= slot.capacity
    week = slot.slot_date - timedelta(days=slot.slot_date.weekday())
    [cell] = [
        c
        for c in service.space_week_availability(db, slot.space, week, None)
        if c["space_slot_id"] == slot.id
    ]
    assert cell["booked_count"] == held
    assert cell["waitlist_count"] == rows.get("waitlisted", 0)


class TestTheCountsFollowTheRows:
    def test_through_a_bookings_whole_life(self, db):
        _org(db)
        slot = _slot(db, _space(db), capacity=2)
        first = service.create_booking(db, _member(db, 1), slot.id)
        second = service.create_booking(db, _member(db, 2), slot.id)
        third = service.create_booking(db, _member(db, 3), slot.id)
        assert (first.status, second.status, third.status) == ("pending", "pending", "waitlisted")
        _assert_counts_match_rows(db, slot)

        [receipt] = _receipts(db, first)
        mark_receipt_paid(db, receipt, payment_method="cash")
        _assert_counts_match_rows(db, slot)

        service.cancel_booking(db, second, cancelled_by_user_id=None, is_admin=True)
        assert third.status == "pending"
        _assert_counts_match_rows(db, slot)

        [expired] = service.expired_pending_bookings(db, third.payment_due_at + timedelta(seconds=1))
        service.expire_unpaid_booking(db, expired)
        _assert_counts_match_rows(db, slot)

    def test_a_full_slot_of_pending_bookings_takes_nobody_else(self, db):
        _org(db, booking_waitlist_enabled=False)
        slot = _slot(db, _space(db), capacity=2)
        service.create_booking(db, _member(db, 1), slot.id)
        service.create_booking(db, _member(db, 2), slot.id)

        with pytest.raises(service.SlotFull):
            service.create_booking(db, _member(db, 3), slot.id)
        _assert_counts_match_rows(db, slot)


def _statements(db, run):
    seen = []

    def record(conn, cursor, statement, params, context, executemany):
        seen.append(" ".join(statement.split()))

    event.listen(db.get_bind(), "before_cursor_execute", record)
    try:
        run()
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", record)
    return seen


class TestTheSlotIsLocked:
    """Asserted on the statements rather than staged as real contention: the
    ``db`` fixture is one connection in a rolled-back transaction, and a test
    that blocks on a lock is the kind that turns flaky in parallel."""

    def test_booking_counts_under_the_slots_lock(self, db):
        _org(db)
        slot = _slot(db, _space(db))

        seen = _statements(db, lambda: service.create_booking(db, _member(db, 1), slot.id))

        assert any("FROM space_slots" in s and "FOR UPDATE" in s for s in seen)

    def test_the_sweep_skips_a_booking_being_paid(self, db):
        _org(db)
        slot = _slot(db, _space(db))
        booking = service.create_booking(db, _member(db, 1), slot.id)

        seen = _statements(
            db,
            lambda: service.expired_pending_bookings(
                db, booking.payment_due_at + timedelta(seconds=1)
            ),
        )

        assert any("FROM bookings" in s and "SKIP LOCKED" in s for s in seen)


class TestTheGatewayRefusesAMethodTheSpaceDoesNotAccept:
    @pytest.mark.parametrize(
        "path, body",
        [("stripe/checkout", None), ("redsys/initiate", {"method": "card"})],
    )
    def test_card_on_a_cash_only_booking(self, client, db, path, body):
        _org(db)
        _stripe_provider(db)
        _create_redsys_provider(db)
        slot = _slot(db, _space(db, methods=("cash",)))
        booking = service.create_booking(db, _member(db, 1), slot.id)
        [receipt] = _receipts(db, booking)
        admin = _create_admin(db, f"booking-gw-{path[:6]}")
        db.commit()

        resp = client.post(
            f"/api/v1/receipts/{receipt.id}/{path}", json=body, cookies=_auth_cookie(admin)
        )

        assert resp.status_code == 400, resp.text
        assert resp.json()["detail"] == {"code": "payment_method_not_accepted", "method": "card"}
