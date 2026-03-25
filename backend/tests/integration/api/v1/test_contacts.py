"""Integration tests for contact management endpoints."""

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.persons.models import Contact, ContactType, Person


def _create_user(db, role="admin", suffix=""):
    person = Person(first_name="Contact", last_name=f"Test{suffix}", email=f"contact-{role}{suffix}@test.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=f"contact-{role}{suffix}@test.com",
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user, person


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id, user.role)}


def _ensure_contact_type(db, code="phone_mobile"):
    ct = db.query(ContactType).filter(ContactType.code == code).first()
    if not ct:
        ct = ContactType(code=code, name="Mobile Phone", is_active=True)
        db.add(ct)
        db.flush()
    return ct


class TestContactsCRUD:
    def test_list_contacts_empty(self, client, db):
        user, person = _create_user(db, "admin", "-list0")
        client.cookies.update(_auth_cookie(user))

        response = client.get(f"/api/v1/persons/{person.id}/contacts/")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_contact(self, client, db):
        user, person = _create_user(db, "admin", "-create")
        ct = _ensure_contact_type(db)
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/persons/{person.id}/contacts/",
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
            entity_type="person", entity_id=person.id,
            contact_type_id=ct.id, value="+34 611 222 333",
        )
        db.add(contact)
        db.flush()

        client.cookies.update(_auth_cookie(user))
        response = client.get(f"/api/v1/persons/{person.id}/contacts/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["value"] == "+34 611 222 333"

    def test_update_contact(self, client, db):
        user, person = _create_user(db, "admin", "-update")
        ct = _ensure_contact_type(db)
        contact = Contact(
            entity_type="person", entity_id=person.id,
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
            entity_type="person", entity_id=person.id,
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
            f"/api/v1/persons/{person.id}/contacts/",
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
