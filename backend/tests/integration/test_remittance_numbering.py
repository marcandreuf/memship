"""Remittance numbers come from a locked per-year counter.

Receipt numbering moved onto ``InvoiceSequence`` under ``SELECT ... FOR UPDATE``;
remittances stayed on ``COUNT(remittances in year) + 1``, which two concurrent
generations can both read before either inserts. This gives them the same
counter and checks it behaves the same way.
"""

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import event

from app.domains.billing.models import Remittance, RemittanceSequence
from app.domains.billing.remittance_service import generate_remittance_number


def _remittance(number, year=2026, day=15, status="draft"):
    return Remittance(
        remittance_number=number,
        remittance_type="sepa",
        status=status,
        emission_date=date(year, 6, day),
        due_date=date(year, 7, day),
        total_amount=0,
        receipt_count=0,
        creditor_name="Numbering Club",
        creditor_iban="ES9121000418450200051332",
        creditor_bic="CAIXESBBXXX",
        creditor_id="ES12ZZZ12345678",
    )


def _issue(db, year=2026, day=15, status="draft"):
    """Allocate a number and persist a remittance holding it, as callers do."""
    number = generate_remittance_number(db, date(year, 6, day))
    db.add(_remittance(number, year, day, status))
    db.flush()
    return number


class TestSequential:
    def test_numbers_run_consecutively(self, db):
        assert [_issue(db) for _ in range(3)] == [
            "REM-2026-0001",
            "REM-2026-0002",
            "REM-2026-0003",
        ]

    def test_a_cancelled_number_is_not_reissued(self, db):
        _issue(db)
        _issue(db, status="cancelled")
        assert _issue(db) == "REM-2026-0003"


class TestPerYear:
    def test_each_year_keeps_its_own_counter(self, db):
        assert _issue(db, year=2025) == "REM-2025-0001"
        assert _issue(db, year=2026) == "REM-2026-0001"
        assert _issue(db, year=2025) == "REM-2025-0002"

    def test_the_counter_row_tracks_the_next_number(self, db):
        _issue(db)
        _issue(db)
        row = db.query(RemittanceSequence).filter_by(year=2026).one()
        assert row.next_number == 3


class TestLocking:
    """The counter row must be read under FOR UPDATE.

    Asserts the statement is emitted rather than staging real contention: the
    ``db`` fixture is one connection inside a rolled-back transaction, and a
    test that blocks on a lock is the kind that turns flaky in parallel.
    """

    def test_sequence_row_is_locked(self, db):
        seen = []

        def record(conn, cursor, statement, params, context, executemany):
            seen.append(" ".join(statement.split()))

        event.listen(db.get_bind(), "before_cursor_execute", record)
        try:
            _issue(db)
            _issue(db)
        finally:
            event.remove(db.get_bind(), "before_cursor_execute", record)

        locks = [
            s for s in seen if "remittance_sequences" in s and "FOR UPDATE" in s
        ]
        assert locks, "generate_remittance_number must SELECT ... FOR UPDATE the counter"


class TestCollision:
    def test_a_number_issued_outside_the_counter_is_an_error(self, db):
        """Stepping past a collision would hide a counter that has fallen behind."""
        db.add(_remittance("REM-2026-0001", day=1))
        db.flush()

        with pytest.raises(HTTPException) as exc:
            generate_remittance_number(db, date(2026, 6, 15))
        assert exc.value.status_code == 500
        assert "REM-2026-0001" in exc.value.detail
