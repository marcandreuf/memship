"""Searching by what the lists display: a person's full name (#284).

Each name column used to be matched against the whole query, so "Aina Torrent"
— shown in the table, but in no single column — found nothing.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.domains.billing.models import Receipt
from app.domains.billing.service import build_receipts_query
from app.domains.members.models import Member
from app.domains.members.service import build_members_query
from app.domains.persons.models import Person


def _member(db, first, last, number):
    person = Person(first_name=first, last_name=last, email=f"{number.lower()}@search.test")
    db.add(person)
    db.flush()
    member = Member(person_id=person.id, member_number=number, status="active")
    db.add(member)
    db.flush()
    return member


def _receipt(db, member, number, description):
    receipt = Receipt(
        receipt_number=number, member_id=member.id, origin="manual",
        description=description, base_amount=Decimal("10.00"),
        vat_rate=Decimal("0.00"), vat_amount=Decimal("0.00"),
        total_amount=Decimal("10.00"), status="emitted",
        emission_date=date(2026, 1, 10),
    )
    db.add(receipt)
    db.flush()
    return receipt


@pytest.fixture
def people(db):
    return {
        "aina": _member(db, "Aina", "Torrent Puig", "S-0001"),
        "joan": _member(db, "Joan", "Torrent", "S-0002"),
        "under": _member(db, "Pau", "Vidal", "S_0003"),
    }


def _member_ids(db, search):
    return {m.id for m in build_members_query(db, search=search).all()}


@pytest.mark.parametrize(
    "search",
    ["Aina Torrent", "aina torrent puig", "Torrent Aina", "  Aina   Torrent ", "Aina S-0001"],
)
def test_member_found_by_what_the_table_shows(db, people, search):
    assert _member_ids(db, search) == {people["aina"].id}


def test_every_word_must_match(db, people):
    assert _member_ids(db, "Torrent") == {people["aina"].id, people["joan"].id}
    assert _member_ids(db, "Joan Puig") == set()


def test_like_wildcards_are_literal(db, people):
    """``_`` matched any single character, so it found every member."""
    assert _member_ids(db, "_") == {people["under"].id}
    assert _member_ids(db, "%") == set()


def test_receipts_found_by_full_name(db, people):
    aina = [_receipt(db, people["aina"], f"R-A{i}", "Cuota anual") for i in range(3)]
    _receipt(db, people["joan"], "R-J1", "Cuota anual")

    found = {r.id for r in build_receipts_query(db, search="Aina Torrent").all()}

    assert found == {r.id for r in aina}


def test_receipt_words_can_span_name_and_description(db, people):
    annual = _receipt(db, people["aina"], "R-A1", "Cuota anual")
    _receipt(db, people["aina"], "R-A2", "Pista de pádel")

    found = {r.id for r in build_receipts_query(db, search="Aina anual").all()}

    assert found == {annual.id}
