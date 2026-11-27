"""``party.email`` becomes a cache of the primary email contact (#473).

The address the organisation writes to moves into ``contacts``, where #473 said
it belongs: the ``email`` channel and the one-primary-per-channel index already
existed and nothing read them. What was missing was a contact *type* meaning
"the main address" — the seeded email types are ``email_work`` and
``email_other``, both explicitly secondary — so ``email_main`` is new.

``party.email`` stays. Six places read the mailing address through it, three of
them Celery tasks and one the opt-out lookup in ``core.email``, and repointing
all six in the same change as the schema move would be far larger and riskier
than this issue implies. A trigger keeps the column equal to the contact, which
is the same device ``trg_party_display_name`` already uses for the display name.

These tests pin the trigger, not the Python: the point of putting the rule in
the database is that it holds for a writer nobody has added yet.
"""

import pytest
from sqlalchemy import text

from app.domains.persons.models import Contact, ContactType, Party, Person
from app.domains.persons.service import (
    PRIMARY_EMAIL_TYPE_CODE,
    set_primary_email_contact,
)


@pytest.fixture
def email_type(db):
    ct = (
        db.query(ContactType)
        .filter(ContactType.code == PRIMARY_EMAIL_TYPE_CODE)
        .first()
    )
    if ct is None:
        ct = ContactType(
            code=PRIMARY_EMAIL_TYPE_CODE, name="Main Email",
            description="The address the organisation writes to",
            channel="email", is_active=True, display_order=0,
        )
        db.add(ct)
        db.flush()
    return ct


def _person(db, first="Cache", last="Target"):
    person = Person(first_name=first, last_name=last)
    db.add(person)
    db.flush()
    return person


class TestTheTriggerMaintainsTheCache:
    def test_a_new_primary_email_contact_fills_the_column(
        self, db, email_type
    ):
        person = _person(db)
        db.add(
            Contact(
                party_id=person.party_id, contact_type_id=email_type.id,
                value="cache-new@example.com", is_primary=True,
            )
        )
        db.flush()
        db.expire_all()

        party = db.query(Party).filter(Party.id == person.party_id).first()
        assert party.email == "cache-new@example.com"

    def test_editing_the_contact_moves_the_column(self, db, email_type):
        person = _person(db)
        contact = Contact(
            party_id=person.party_id, contact_type_id=email_type.id,
            value="cache-before@example.com", is_primary=True,
        )
        db.add(contact)
        db.flush()

        contact.value = "cache-after@example.com"
        db.flush()
        db.expire_all()

        party = db.query(Party).filter(Party.id == person.party_id).first()
        assert party.email == "cache-after@example.com"

    def test_deleting_the_contact_clears_the_column(self, db, email_type):
        person = _person(db)
        contact = Contact(
            party_id=person.party_id, contact_type_id=email_type.id,
            value="cache-gone@example.com", is_primary=True,
        )
        db.add(contact)
        db.flush()

        db.delete(contact)
        db.flush()
        db.expire_all()

        party = db.query(Party).filter(Party.id == person.party_id).first()
        assert party.email is None

    def test_a_phone_contact_does_not_touch_the_address(self, db, email_type):
        """The trigger fires on every contact row, so it has to filter."""
        phone_type = (
            db.query(ContactType).filter(ContactType.code == "phone_mobile").first()
        )
        if phone_type is None:
            phone_type = ContactType(
                code="phone_mobile", name="Mobile", channel="phone",
                is_active=True, display_order=2,
            )
            db.add(phone_type)
            db.flush()

        person = _person(db)
        set_primary_email_contact(db, person.party_id, "cache-keep@example.com")
        db.add(
            Contact(
                party_id=person.party_id, contact_type_id=phone_type.id,
                value="+34600000000", is_primary=True,
            )
        )
        db.flush()
        db.expire_all()

        party = db.query(Party).filter(Party.id == person.party_id).first()
        assert party.email == "cache-keep@example.com"

    def test_promoting_a_second_address_moves_the_column_to_it(
        self, db, email_type
    ):
        """Demote-then-promote is two statements, and the cache must end on the
        winner whichever order they land in."""
        other_type = (
            db.query(ContactType).filter(ContactType.code == "email_other").first()
        )
        if other_type is None:
            other_type = ContactType(
                code="email_other", name="Other Email", channel="email",
                is_active=True, display_order=6,
            )
            db.add(other_type)
            db.flush()

        person = _person(db)
        set_primary_email_contact(db, person.party_id, "cache-first@example.com")

        db.add(
            Contact(
                party_id=person.party_id, contact_type_id=other_type.id,
                value="cache-second@example.com", is_primary=True,
            )
        )
        db.flush()
        db.expire_all()

        party = db.query(Party).filter(Party.id == person.party_id).first()
        assert party.email == "cache-second@example.com"
        # And exactly one primary survived the demotion.
        assert (
            db.query(Contact)
            .filter(
                Contact.party_id == person.party_id,
                Contact.channel == "email",
                Contact.is_primary.is_(True),
            )
            .count()
            == 1
        )


class TestTheServiceWritesTheContact:
    def test_it_creates_the_contact_and_the_column_follows(self, db, email_type):
        person = _person(db)

        set_primary_email_contact(db, person.party_id, "svc-new@example.com")
        db.expire_all()

        contact = (
            db.query(Contact)
            .filter(Contact.party_id == person.party_id, Contact.is_primary.is_(True))
            .first()
        )
        assert contact is not None
        assert contact.value == "svc-new@example.com"
        assert contact.channel == "email"
        party = db.query(Party).filter(Party.id == person.party_id).first()
        assert party.email == "svc-new@example.com"

    def test_it_reuses_the_contact_rather_than_adding_a_second(
        self, db, email_type
    ):
        person = _person(db)
        set_primary_email_contact(db, person.party_id, "svc-one@example.com")
        set_primary_email_contact(db, person.party_id, "svc-two@example.com")
        db.expire_all()

        assert (
            db.query(Contact)
            .filter(Contact.party_id == person.party_id, Contact.channel == "email")
            .count()
            == 1
        )
        party = db.query(Party).filter(Party.id == person.party_id).first()
        assert party.email == "svc-two@example.com"

    def test_a_blank_address_removes_the_contact_and_nulls_the_column(
        self, db, email_type
    ):
        """Not an empty string: every mail path tests the address for
        truthiness, and `""` would read as one it can send to."""
        person = _person(db)
        set_primary_email_contact(db, person.party_id, "svc-clear@example.com")

        set_primary_email_contact(db, person.party_id, None)
        db.expire_all()

        assert (
            db.query(Contact)
            .filter(Contact.party_id == person.party_id, Contact.channel == "email")
            .count()
            == 0
        )
        party = db.query(Party).filter(Party.id == person.party_id).first()
        assert party.email is None


class TestTheTriggerIsInTheTestSchemaAtAll:
    def test_create_all_installs_it(self, db):
        """Pinned because the migration and `create_all` are separate copies.

        If only the migration carried it, every test above would pass against a
        schema that does not match a deployed one.
        """
        found = db.execute(
            text("SELECT count(*) FROM pg_trigger WHERE tgname = 'trg_party_email_from_contact'")
        ).scalar()
        assert found == 1
