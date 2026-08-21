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
        person_id=person.id,
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
            member_id=member.id,
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
