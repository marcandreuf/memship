"""Integration tests for contact management endpoints."""

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.persons.models import Contact, ContactType, Person


def _create_user(db, role="admin", suffix=""):
    person = Person(first_name="Contact", last_name=f"Test{suffix}", email=f"contact-{role}{suffix}@examplee6e3b1.com")
    db.add(person)
    db.flush()
    user = User(
        party_id=person.party_id,
        email=f"contact-{role}{suffix}@examplee6e3b1.com",
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user, person


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id)}


def _ensure_contact_type(db, code="phone_mobile"):
    ct = db.query(ContactType).filter(ContactType.code == code).first()
    if not ct:
        ct = ContactType(code=code, name="Mobile Phone", channel="phone", is_active=True)
        db.add(ct)
        db.flush()
    return ct


def _contact_type(db, code, channel, name=None):
    """Fetch or create a type in a given channel. Several types share a channel
    (``phone_home`` and ``phone_mobile`` are both ``phone``), which is what the
    one-primary-per-channel index is about."""
    ct = db.query(ContactType).filter(ContactType.code == code).first()
    if not ct:
        ct = ContactType(
            code=code, name=name or code, channel=channel, is_active=True
        )
        db.add(ct)
        db.flush()
    return ct


def _contact(db, party_id, contact_type, value, *, is_primary=False):
    row = Contact(
        party_id=party_id,
        contact_type_id=contact_type.id,
        value=value,
        is_primary=is_primary,
    )
    db.add(row)
    db.flush()
    return row


class TestContactsCRUD:
    def test_list_contacts_empty(self, client, db):
        user, person = _create_user(db, "admin", "-list0")
        client.cookies.update(_auth_cookie(user))

        response = client.get(f"/api/v1/persons/{person.party_id}/contacts/")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_contact(self, client, db):
        user, person = _create_user(db, "admin", "-create")
        ct = _ensure_contact_type(db)
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/persons/{person.party_id}/contacts/",
            json={"contact_type_id": ct.id, "value": "+34 600 123 456", "is_primary": True},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["value"] == "+34 600 123 456"
        assert data["is_primary"] is True
        assert data["contact_type_name"] == "Mobile Phone"

    def test_list_contacts_after_create(self, client, db):
        user, person = _create_user(db, "admin", "-list1")
        ct = _ensure_contact_type(db)
        contact = Contact(
            party_id=person.party_id,
            contact_type_id=ct.id, value="+34 611 222 333",
        )
        db.add(contact)
        db.flush()

        client.cookies.update(_auth_cookie(user))
        response = client.get(f"/api/v1/persons/{person.party_id}/contacts/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["value"] == "+34 611 222 333"

    def test_update_contact(self, client, db):
        user, person = _create_user(db, "admin", "-update")
        ct = _ensure_contact_type(db)
        contact = Contact(
            party_id=person.party_id,
            contact_type_id=ct.id, value="+34 600 000 000",
        )
        db.add(contact)
        db.flush()

        client.cookies.update(_auth_cookie(user))
        response = client.put(
            f"/api/v1/contacts/{contact.id}",
            json={"value": "+34 699 999 999", "label": "Personal"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["value"] == "+34 699 999 999"
        assert data["label"] == "Personal"

    def test_delete_contact(self, client, db):
        user, person = _create_user(db, "admin", "-delete")
        ct = _ensure_contact_type(db)
        contact = Contact(
            party_id=person.party_id,
            contact_type_id=ct.id, value="+34 600 111 222",
        )
        db.add(contact)
        db.flush()

        client.cookies.update(_auth_cookie(user))
        response = client.delete(f"/api/v1/contacts/{contact.id}")
        assert response.status_code == 204

    def test_create_contact_requires_admin(self, client, db):
        user, person = _create_user(db, "member", "-rbac")
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/persons/{person.party_id}/contacts/",
            json={"value": "+34 600 000 000"},
        )
        assert response.status_code == 403

    def test_create_contact_person_not_found(self, client, db):
        user, _ = _create_user(db, "admin", "-notfound")
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            "/api/v1/persons/99999/contacts/",
            json={"value": "+34 600 000 000"},
        )
        assert response.status_code == 404


class TestOnePrimaryPerChannel:
    """``uq_contacts_one_primary_per_channel`` permits one primary per channel,
    and a channel holds several types: ``phone_home``, ``phone_mobile``,
    ``phone_work`` and ``phone_emergency`` are all ``phone``.

    A primary home phone beside a primary mobile was legal before the index, and
    nothing demotes the incumbent on a write, so the insert collided with the
    index and the unhandled ``IntegrityError`` surfaced as a 500 on an action
    that had always worked.

    The rule is newest-wins: the contact being saved takes the slot. That is the
    opposite of the migration's dedupe, which keeps the first per channel, and
    the asymmetry is deliberate - at upgrade there is no user intent to read,
    here somebody ticked the box.
    """

    def test_a_new_primary_demotes_the_incumbent_in_the_same_channel(self, client, db):
        user, person = _create_user(db, "admin", "-prim-new")
        home = _contact_type(db, "phone_home", "phone", "Home Phone")
        mobile = _contact_type(db, "phone_mobile", "phone", "Mobile Phone")
        incumbent = _contact(db, person.party_id, home, "+34 900 000 001", is_primary=True)
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/persons/{person.party_id}/contacts/",
            json={"contact_type_id": mobile.id, "value": "+34 600 000 001", "is_primary": True},
        )

        assert response.status_code == 201
        assert response.json()["is_primary"] is True
        db.refresh(incumbent)
        assert incumbent.is_primary is False

    def test_promoting_an_existing_contact_demotes_the_incumbent(self, client, db):
        user, person = _create_user(db, "admin", "-prim-promote")
        home = _contact_type(db, "phone_home", "phone", "Home Phone")
        mobile = _contact_type(db, "phone_mobile", "phone", "Mobile Phone")
        incumbent = _contact(db, person.party_id, home, "+34 900 000 002", is_primary=True)
        challenger = _contact(db, person.party_id, mobile, "+34 600 000 002")
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            f"/api/v1/contacts/{challenger.id}", json={"is_primary": True}
        )

        assert response.status_code == 200
        db.refresh(incumbent)
        db.refresh(challenger)
        assert challenger.is_primary is True
        assert incumbent.is_primary is False

    def test_retyping_into_a_channel_that_already_has_a_primary_demotes_it(
        self, client, db
    ):
        """Changing a primary contact's type can move it into a channel that
        already has one, which the composite FK allows and the index does not."""
        user, person = _create_user(db, "admin", "-prim-retype")
        home = _contact_type(db, "phone_home", "phone", "Home Phone")
        mobile = _contact_type(db, "phone_mobile", "phone", "Mobile Phone")
        work_email = _contact_type(db, "email_work", "email", "Work Email")
        incumbent = _contact(db, person.party_id, home, "+34 900 000 003", is_primary=True)
        moving = _contact(db, person.party_id, work_email, "a@examplee6e3b1.com", is_primary=True)
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            f"/api/v1/contacts/{moving.id}", json={"contact_type_id": mobile.id}
        )

        assert response.status_code == 200
        db.refresh(incumbent)
        db.refresh(moving)
        assert moving.is_primary is True
        assert incumbent.is_primary is False

    def test_a_primary_email_and_a_primary_phone_coexist(self, client, db):
        """The index's actual purpose, kept as a guard on the demotion: the
        demotion must be scoped to one channel and not clear the other."""
        user, person = _create_user(db, "admin", "-prim-channels")
        mobile = _contact_type(db, "phone_mobile", "phone", "Mobile Phone")
        work_email = _contact_type(db, "email_work", "email", "Work Email")
        phone = _contact(db, person.party_id, mobile, "+34 600 000 004", is_primary=True)
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/persons/{person.party_id}/contacts/",
            json={"contact_type_id": work_email.id, "value": "b@examplee6e3b1.com", "is_primary": True},
        )

        assert response.status_code == 201
        db.refresh(phone)
        assert phone.is_primary is True


class TestTheClientCanGroupByChannel:
    """The cap and the primary slot are both per channel, and a channel holds
    several types, so the client has to be told which channel a type belongs
    to rather than inferring it from the code."""

    def test_contact_types_carry_their_channel(self, client, db):
        user, _ = _create_user(db, "admin", "-chan-types")
        _contact_type(db, "phone_home", "phone", "Home Phone")
        _contact_type(db, "email_work", "email", "Work Email")
        client.cookies.update(_auth_cookie(user))

        response = client.get("/api/v1/contact-types/")

        assert response.status_code == 200
        by_code = {t["code"]: t for t in response.json()}
        assert by_code["phone_home"]["channel"] == "phone"
        assert by_code["email_work"]["channel"] == "email"

    def test_a_saved_contact_carries_its_channel(self, client, db):
        user, person = _create_user(db, "admin", "-chan-saved")
        mobile = _contact_type(db, "phone_mobile", "phone", "Mobile Phone")
        _contact(db, person.party_id, mobile, "+34 600 000 009")
        client.cookies.update(_auth_cookie(user))

        response = client.get(f"/api/v1/persons/{person.party_id}/contacts/")

        assert response.status_code == 200
        assert response.json()[0]["channel"] == "phone"
