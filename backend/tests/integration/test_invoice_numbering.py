"""Receipt numbers must be sequential and unbroken.

The number used to be COUNT(receipts in that year, is_active) + 1, so
deactivating one receipt shifted the number of every receipt issued after it,
and the loop that guarded against the resulting collision skipped numbers —
manufacturing the gaps it was there to prevent. Spanish invoicing practice
expects the series to be sequential and unbroken; a counter is the only shape
that gives that.
"""

from datetime import date

import pytest

from app.domains.billing.models import InvoiceSequence, Receipt
from app.domains.billing.service import generate_receipt_number
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


@pytest.fixture
def org(db):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(id=1, name="Numbering Club", default_vat_rate=21)
        db.add(org)
    org.invoice_prefix = "FAC"
    org.invoice_annual_reset = True
    db.flush()
    return org


@pytest.fixture
def member(db):
    mt = db.query(MembershipType).first()
    if not mt:
        mt = MembershipType(name="Numbering", slug="numbering", is_active=True)
        db.add(mt)
        db.flush()
    person = Person(
        first_name="Num", last_name="Bering", email="num@examplee6e3b1.com"
    )
    db.add(person)
    db.flush()
    m = Member(
        party_id=person.party_id,
        membership_type_id=mt.id,
        member_number="NUM-0001",
        status="active",
    )
    db.add(m)
    db.flush()
    return m


def _issue(db, member, year=2026, day=15):
    """Allocate a number and persist a receipt holding it, as callers do."""
    number = generate_receipt_number(db, date(year, 6, day))
    db.add(
        Receipt(
            receipt_number=number,
            party_id=member.party_id,
            emission_date=date(year, 6, day),
            due_date=date(year, 7, day),
            base_amount=10,
            vat_rate=0,
            vat_amount=0,
            total_amount=10,
            origin="manual",
            description="Numbering probe",
            status="pending",
            is_active=True,
        )
    )
    db.flush()
    return number


class TestSequential:
    def test_numbers_run_consecutively(self, db, org, member):
        got = [_issue(db, member) for _ in range(5)]
        assert got == [
            "FAC-2026-0001",
            "FAC-2026-0002",
            "FAC-2026-0003",
            "FAC-2026-0004",
            "FAC-2026-0005",
        ]

    def test_a_deactivated_receipt_does_not_shift_later_numbers(self, db, org, member):
        """The defect, directly.

        With COUNT-based numbering, deactivating FAC-2026-0002 made the next
        receipt FAC-2026-0003 a second time — a duplicate the collision loop then
        "fixed" by skipping to 0004, leaving a gap and a reused number.
        """
        first, second, third = _issue(db, member), _issue(db, member), _issue(db, member)
        assert (first, second, third) == (
            "FAC-2026-0001",
            "FAC-2026-0002",
            "FAC-2026-0003",
        )

        db.query(Receipt).filter(Receipt.receipt_number == second).update(
            {"is_active": False}
        )
        db.flush()

        assert _issue(db, member) == "FAC-2026-0004"

    def test_a_cancelled_number_is_not_reissued(self, db, org, member):
        """A spent number stays spent — that is what makes the series auditable."""
        first = _issue(db, member)
        db.query(Receipt).filter(Receipt.receipt_number == first).update(
            {"status": "cancelled"}
        )
        db.flush()

        assert _issue(db, member) == "FAC-2026-0002"


class TestPerYear:
    def test_each_year_keeps_its_own_counter(self, db, org, member):
        assert _issue(db, member, year=2026) == "FAC-2026-0001"
        assert _issue(db, member, year=2026) == "FAC-2026-0002"
        assert _issue(db, member, year=2027) == "FAC-2027-0001"
        assert _issue(db, member, year=2026) == "FAC-2026-0003"

    def test_backdating_does_not_disturb_the_current_year(self, db, org, member):
        """A receipt dated into a closed year draws from that year's series."""
        _issue(db, member, year=2026)
        _issue(db, member, year=2026)
        assert _issue(db, member, year=2025) == "FAC-2025-0001"
        assert _issue(db, member, year=2026) == "FAC-2026-0003"

    def test_the_counter_row_tracks_the_next_number(self, db, org, member):
        _issue(db, member, year=2026)
        _issue(db, member, year=2026)
        row = (
            db.query(InvoiceSequence).filter(InvoiceSequence.year == 2026).one()
        )
        assert row.next_number == 3


class TestGlobalMode:
    def test_annual_reset_off_uses_the_org_counter(self, db, org, member):
        org.invoice_annual_reset = False
        org.invoice_next_number = 41
        db.flush()

        assert _issue(db, member, year=2026) == "FAC-2026-0041"
        assert _issue(db, member, year=2027) == "FAC-2027-0042"


class TestItLocksTheOrgRowOnlyWhenItIsTheCounter:
    """The lock has to follow the write, not the read.

    Numbering used to take ``SELECT ... FOR UPDATE`` on ``organization_settings``
    in both modes, while in the default annual mode it only reads
    ``invoice_prefix`` from that row and the number comes from
    ``InvoiceSequence`` under its own lock. A billing run calls this once per
    member inside one transaction, and a row lock is held until commit, so the
    whole application serialised on the run: 4,265 members measured 20.9 s with
    a concurrent member sign-up waiting 18.9 s of it (memship#459 §1).

    Asserted on the emitted SQL rather than on a timing, because the defect was
    never a slow query. The statement is correct in isolation and only wrong in
    what it holds, so a test that watches for the wait would need a second
    connection and would still pass on a fast machine.
    """

    @staticmethod
    def _org_locks(db, fn):
        """Statements that lock the settings row while ``fn`` runs."""
        seen = []

        def record(conn, cursor, statement, params, context, executemany):
            collapsed = " ".join(statement.split()).upper()
            if "ORGANIZATION_SETTINGS" in collapsed and "FOR UPDATE" in collapsed:
                seen.append(collapsed)

        from sqlalchemy import event

        bind = db.get_bind()
        event.listen(bind, "before_cursor_execute", record)
        try:
            fn()
        finally:
            event.remove(bind, "before_cursor_execute", record)
        return seen

    def test_annual_mode_does_not_lock_it(self, db, org, member):
        org.invoice_annual_reset = True
        db.flush()

        locks = self._org_locks(db, lambda: _issue(db, member, year=2026))

        assert locks == [], f"settings row locked to read a prefix: {locks}"

    def test_global_mode_still_locks_it(self, db, org, member):
        """The counter lives on the row here, so two concurrent callers would
        otherwise read the same number and issue it twice."""
        org.invoice_annual_reset = False
        org.invoice_next_number = 7
        db.flush()

        locks = self._org_locks(db, lambda: _issue(db, member, year=2026))

        assert len(locks) == 1, f"expected exactly one locking read, got {locks}"

    def test_a_caller_supplied_row_is_not_trusted_for_the_counter(self, db, org, member):
        """Passing the row in saves a read per receipt in a bulk run, and must
        not become a way to reissue a number: the non-annual branch re-reads
        under the lock, so the number still advances."""
        org.invoice_annual_reset = False
        org.invoice_next_number = 50
        db.flush()

        first = generate_receipt_number(db, date(2026, 6, 15), org)
        second = generate_receipt_number(db, date(2026, 6, 15), org)

        assert (first, second) == ("FAC-2026-0050", "FAC-2026-0051")
