"""Integration tests for membership type endpoints."""

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.members.models import MembershipType
from app.domains.persons.models import Person


def _create_user(db, role="admin"):
    person = Person(first_name="Admin", last_name="User", email=f"{role}@test.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=f"{role}@test.com",
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _auth_cookie(user):
    token = create_access_token(user.id, user.role)
    return {"access_token": token}


class TestMembershipTypeCRUD:
    def test_create_membership_type(self, client, db):
        user = _create_user(db, "admin")
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            "/api/v1/membership-types/",
            json={
                "name": "Premium",
                "slug": "premium",
                "description": "Premium membership",
                "base_price": 50.0,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Premium"
        assert data["slug"] == "premium"
        assert data["base_price"] == 50.0

    def test_list_membership_types(self, client, db):
        user = _create_user(db, "member")
        db.add(MembershipType(name="Basic", slug="basic", is_active=True))
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.get("/api/v1/membership-types/")
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_update_membership_type(self, client, db):
        user = _create_user(db, "admin")
        mt = MembershipType(name="Old", slug="old", is_active=True)
        db.add(mt)
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            f"/api/v1/membership-types/{mt.id}",
            json={"name": "Updated"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated"

    def test_delete_membership_type(self, client, db):
        user = _create_user(db, "admin")
        mt = MembershipType(name="ToDelete", slug="to-delete", is_active=True)
        db.add(mt)
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.delete(f"/api/v1/membership-types/{mt.id}")
        assert response.status_code == 204

    def test_member_cannot_create(self, client, db):
        user = _create_user(db, "member")
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            "/api/v1/membership-types/",
            json={"name": "Blocked", "slug": "blocked"},
        )
        assert response.status_code == 403

    def test_duplicate_slug(self, client, db):
        user = _create_user(db, "admin")
        db.add(MembershipType(name="Existing", slug="existing", is_active=True))
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            "/api/v1/membership-types/",
            json={"name": "Another", "slug": "existing"},
        )
        assert response.status_code == 409
