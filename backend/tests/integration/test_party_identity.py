"""The party identity root (ADR 0003, phase 1).

Every person is a party; a party need not be a person. These tests pin the
three guarantees the supertype was built for: creation is automatic and
faithful, non-person parties exist without a subtype or a membership, and
the composite foreign key makes subtypes mutually exclusive.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.domains.persons.models import Party, PartyKind, Person


def _person(**overrides):
    fields = {"first_name": "Nuria", "last_name": "Vidal"}
    fields.update(overrides)
    return Person(**fields)


class TestPersonCreatesItsParty:
    def test_new_person_gets_a_party_row(self, db):
        person = _person(email="nuria@example.com", national_id="12345678Z")
        db.add(person)
        db.flush()

        party = db.get(Party, person.party_id)
        assert party is not None
        assert party.kind == "person"
        assert party.display_name == "Nuria Vidal"
        assert party.national_id == "12345678Z"
        assert party.email == "nuria@example.com"

    def test_the_pinned_kind_is_person(self, db):
        person = _person()
        db.add(person)
        db.flush()
        assert person.kind == "person"

    def test_two_persons_get_distinct_parties(self, db):
        first, second = _person(), _person(first_name="Pau")
        db.add_all([first, second])
        db.flush()
        assert first.party_id != second.party_id


class TestNonPersonParties:
    def test_a_company_needs_no_subtype_and_no_membership(self, db):
        company = Party(kind="company", display_name="Acme Donations SL",
                        national_id="B12345678")
        db.add(company)
        db.flush()

        subtype_rows = db.query(Person).filter(Person.party_id == company.id).count()
        assert subtype_rows == 0

    def test_kinds_are_registry_rows(self, db):
        codes = {kind.code for kind in db.query(PartyKind).all()}
        assert codes == {"person", "company", "association", "public_body",
                         "foundation", "other"}


class TestSubtypeExclusivity:
    def test_a_company_cannot_hold_a_persons_row(self, db):
        """The composite FK: persons attach only to parties of kind 'person'."""
        company = Party(kind="company", display_name="Acme Donations SL")
        db.add(company)
        db.flush()

        db.add(_person(party_id=company.id))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_one_party_cannot_hold_two_persons_rows(self, db):
        person = _person()
        db.add(person)
        db.flush()

        db.add(_person(first_name="Impostor", party_id=person.party_id))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_deleting_a_party_cascades_its_person(self, db):
        person = _person()
        db.add(person)
        db.flush()
        person_id, party_id = person.id, person.party_id
        db.expunge(person)

        db.execute(text("DELETE FROM party WHERE id = :id"), {"id": party_id})
        assert db.get(Person, person_id) is None


class TestPhase2Repoint:
    """Phase 2: login and membership are facts about a party."""

    def test_renaming_a_person_updates_the_party_display_name(self, db):
        person = _person()
        db.add(person)
        db.flush()

        person.last_name = "Casals"
        db.flush()
        db.expire_all()

        assert db.get(Party, person.party_id).display_name == "Nuria Casals"

    def test_one_active_login_per_party(self, db):
        from app.domains.auth.models import User

        person = _person()
        db.add(person)
        db.flush()
        db.add(User(party_id=person.party_id, email="a@example.com", is_active=True))
        db.flush()

        db.add(User(party_id=person.party_id, email="b@example.com", is_active=True))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_a_deactivated_login_may_share_the_party(self, db):
        """The index is partial on purpose: deactivated duplicates are history."""
        from app.domains.auth.models import User

        person = _person()
        db.add(person)
        db.flush()
        db.add(User(party_id=person.party_id, email="a2@example.com", is_active=True))
        db.add(User(party_id=person.party_id, email="b2@example.com", is_active=False))
        db.flush()

    def test_one_active_membership_per_party(self, db):
        from app.domains.members.models import Member

        person = _person()
        db.add(person)
        db.flush()
        db.add(Member(party_id=person.party_id, is_active=True))
        db.flush()

        db.add(Member(party_id=person.party_id, is_active=True))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_the_member_resolves_its_login_through_the_party(self, db):
        from app.domains.auth.models import User
        from app.domains.members.models import Member

        person = _person()
        db.add(person)
        db.flush()
        user = User(party_id=person.party_id, email="link@example.com", is_active=True)
        member = Member(party_id=person.party_id)
        db.add_all([user, member])
        db.flush()
        db.expire_all()

        member = db.get(Member, member.id)
        assert member.user is not None and member.user.id == user.id
        assert member.person is not None and member.person.party_id == person.party_id
