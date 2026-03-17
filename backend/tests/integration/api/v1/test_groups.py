"""Integration tests for group endpoints."""

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.members.models import Group
from app.domains.persons.models import Person


def _create_user(db, role="admin"):
    person = Person(first_name="Test", last_name="User", email=f"group-{role}@test.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=f"group-{role}@test.com",
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id, user.role)}


class TestGroupCRUD:
    def test_create_group(self, client, db):
        user = _create_user(db, "admin")
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            "/api/v1/groups/",
            json={"name": "Youth", "slug": "youth", "description": "Youth programs"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Youth"
        assert data["slug"] == "youth"

    def test_list_groups(self, client, db):
        user = _create_user(db, "member")
        db.add(Group(name="Adults", slug="adults", is_active=True))
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.get("/api/v1/groups/")
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_update_group(self, client, db):
        user = _create_user(db, "admin")
        group = Group(name="Old", slug="old", is_active=True)
        db.add(group)
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            f"/api/v1/groups/{group.id}",
            json={"name": "Updated"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated"

    def test_delete_group(self, client, db):
        user = _create_user(db, "admin")
        group = Group(name="ToDelete", slug="to-delete", is_active=True)
        db.add(group)
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.delete(f"/api/v1/groups/{group.id}")
        assert response.status_code == 204

    def test_member_cannot_create(self, client, db):
        user = _create_user(db, "member")
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            "/api/v1/groups/",
            json={"name": "Blocked", "slug": "blocked"},
        )
        assert response.status_code == 403

    def test_duplicate_slug(self, client, db):
        user = _create_user(db, "admin")
        db.add(Group(name="Existing", slug="existing", is_active=True))
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            "/api/v1/groups/",
            json={"name": "Another", "slug": "existing"},
        )
        assert response.status_code == 409
