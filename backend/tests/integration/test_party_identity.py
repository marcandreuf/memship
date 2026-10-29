"""The party identity root (ADR 0003, phase 1).

Every person is a party; a party need not be a person. These tests pin the
three guarantees the supertype was built for: creation is automatic and
faithful, non-person parties exist without a subtype or a membership, and
the composite foreign key makes subtypes mutually exclusive.
"""

import datetime

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
        party_id = person.party_id
        db.expunge(person)

        db.execute(text("DELETE FROM party WHERE id = :id"), {"id": party_id})
        assert db.get(Person, party_id) is None


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


class TestPhase3RealOwners:
    """Phase 3: addresses and contacts belong to something that exists."""

    def test_an_address_must_have_exactly_one_owner(self, db):
        from app.domains.persons.models import Address

        db.add(Address(address_line1="Nowhere 1", city="Barcelona"))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_an_address_cannot_serve_two_masters(self, db):
        from app.domains.bookings.models import Space
        from app.domains.persons.models import Address

        person = _person()
        space = Space(name="Court A", open_time=datetime.time(8), close_time=datetime.time(22))
        db.add_all([person, space])
        db.flush()

        db.add(Address(
            party_id=person.party_id, space_id=space.id,
            address_line1="Twice-owned 2", city="Barcelona",
        ))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_deleting_the_party_takes_its_addresses_along(self, db):
        from app.domains.persons.models import Address

        person = _person()
        db.add(person)
        db.flush()
        address = Address(party_id=person.party_id, address_line1="Gone 3", city="Girona")
        db.add(address)
        db.flush()
        address_id = address.id
        db.expunge_all()

        db.execute(text("DELETE FROM party WHERE id = :id"), {"id": person.party_id})
        assert db.get(Address, address_id) is None

    def test_one_primary_address_per_party(self, db):
        from app.domains.persons.models import Address

        person = _person()
        db.add(person)
        db.flush()
        db.add(Address(party_id=person.party_id, address_line1="First 4", city="Reus", is_primary=True))
        db.flush()
        db.add(Address(party_id=person.party_id, address_line1="Second 5", city="Reus", is_primary=True))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_a_contacts_channel_follows_its_type(self, db):
        from app.domains.persons.models import Contact, ContactType

        person = _person()
        ct = ContactType(code="phone_p3", name="Phone", channel="phone")
        db.add_all([person, ct])
        db.flush()

        contact = Contact(party_id=person.party_id, contact_type_id=ct.id, value="+34 600 000 001")
        db.add(contact)
        db.flush()
        assert contact.channel == "phone"

    def test_a_primary_email_and_a_primary_phone_coexist(self, db):
        from app.domains.persons.models import Contact, ContactType

        person = _person()
        phone = ContactType(code="phone_p3b", name="Phone", channel="phone")
        email = ContactType(code="email_p3b", name="Email", channel="email")
        db.add_all([person, phone, email])
        db.flush()

        db.add_all([
            Contact(party_id=person.party_id, contact_type_id=phone.id, value="+34 600 000 002", is_primary=True),
            Contact(party_id=person.party_id, contact_type_id=email.id, value="p3@example.org", is_primary=True),
        ])
        db.flush()

    def test_a_second_primary_on_the_same_channel_is_refused(self, db):
        """The index is the backstop; the application is the policy.

        ``_one_primary_contact_per_channel`` hands the slot over before an ORM
        write can collide, so this reaches the constraint through raw SQL -- the
        way a migration, a psql session or a future writer outside the ORM
        would. The same reason the channel-disagreement test below does.
        """
        from app.domains.persons.models import Contact, ContactType

        person = _person()
        home = ContactType(code="phone_p3c1", name="Home", channel="phone")
        work = ContactType(code="phone_p3c2", name="Work", channel="phone")
        db.add_all([person, home, work])
        db.flush()

        db.add(Contact(party_id=person.party_id, contact_type_id=home.id, value="+34 600 000 003", is_primary=True))
        db.flush()

        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    "INSERT INTO contacts "
                    "(party_id, contact_type_id, channel, value, is_primary) "
                    "VALUES (:p, :t, 'phone', '+34 600 000 004', true)"
                ),
                {"p": person.party_id, "t": work.id},
            )

    def test_the_application_demotes_instead_of_colliding(self, db):
        """The other half of the pair: through the ORM the second primary is
        accepted and the first stands down."""
        from app.domains.persons.models import Contact, ContactType

        person = _person()
        home = ContactType(code="phone_p3c3", name="Home", channel="phone")
        work = ContactType(code="phone_p3c4", name="Work", channel="phone")
        db.add_all([person, home, work])
        db.flush()

        first = Contact(party_id=person.party_id, contact_type_id=home.id, value="+34 600 000 005", is_primary=True)
        db.add(first)
        db.flush()
        second = Contact(party_id=person.party_id, contact_type_id=work.id, value="+34 600 000 006", is_primary=True)
        db.add(second)
        db.flush()

        db.refresh(first)
        assert second.is_primary is True
        assert first.is_primary is False

    def test_a_channel_cannot_disagree_with_its_type(self, db):
        from app.domains.persons.models import ContactType

        person = _person()
        ct = ContactType(code="email_p3d", name="Email", channel="email")
        db.add_all([person, ct])
        db.flush()

        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    "INSERT INTO contacts (party_id, contact_type_id, channel, value) "
                    "VALUES (:p, :t, 'phone', 'liar@example.org')"
                ),
                {"p": person.party_id, "t": ct.id},
            )

    def test_the_club_is_a_party(self, db):
        from app.domains.organizations.models import OrganizationSettings

        org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
        if org is None:
            org = OrganizationSettings(id=1, name="Club de Prova")
            db.add(org)
            db.flush()

        party = db.get(Party, org.party_id)
        assert party is not None
        assert party.kind == "association"

    def test_the_person_reads_its_email_from_the_party(self, db):
        person = _person(email="facts@example.org")
        db.add(person)
        db.flush()
        db.expire_all()

        person = db.get(Person, person.party_id)
        assert person.email == "facts@example.org"
        assert db.get(Party, person.party_id).email == "facts@example.org"

        person.email = "edited@example.org"
        db.flush()
        db.expire_all()
        assert db.get(Party, person.party_id).email == "edited@example.org"
