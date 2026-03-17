"""Integration tests for member endpoints."""

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.members.models import Member, MembershipType
from app.domains.persons.models import Person


def _create_admin(db):
    person = Person(first_name="Admin", last_name="User", email="admin-m@test.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email="admin-m@test.com",
        password_hash=hash_password("password123"),
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _create_member_user(db, email="member-m@test.com"):
    person = Person(first_name="Member", last_name="User", email=email)
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=email,
        password_hash=hash_password("password123"),
        role="member",
        is_active=True,
    )
    db.add(user)
    db.flush()

    mt = db.query(MembershipType).first()
    if not mt:
        mt = MembershipType(name="General", slug="general", is_active=True)
        db.add(mt)
        db.flush()

    member = Member(
        person_id=person.id,
        user_id=user.id,
        membership_type_id=mt.id,
        member_number=f"M-{user.id:04d}",
        status="active",
    )
    db.add(member)
    db.flush()
    return user, member


def _ensure_membership_type(db):
    mt = db.query(MembershipType).first()
    if not mt:
        mt = MembershipType(name="General", slug="general", is_active=True)
        db.add(mt)
        db.flush()
    return mt


def _auth_cookie(user):
    token = create_access_token(user.id, user.role)
    return {"access_token": token}


class TestMemberCRUD:
    def test_create_member(self, client, db):
        admin = _create_admin(db)
        mt = _ensure_membership_type(db)
        client.cookies.update(_auth_cookie(admin))

        response = client.post(
            "/api/v1/members/",
            json={
                "first_name": "New",
                "last_name": "Member",
                "email": "new-member@test.com",
                "membership_type_id": mt.id,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["person"]["first_name"] == "New"
        assert data["member_number"] is not None
        assert data["status"] == "pending"

    def test_list_members(self, client, db):
        admin = _create_admin(db)
        _create_member_user(db, "list-member@test.com")
        client.cookies.update(_auth_cookie(admin))

        response = client.get("/api/v1/members/")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "meta" in data
        assert data["meta"]["total"] >= 1

    def test_search_members(self, client, db):
        admin = _create_admin(db)
        _create_member_user(db, "searchable@test.com")
        client.cookies.update(_auth_cookie(admin))

        response = client.get("/api/v1/members/?search=searchable")
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) >= 1

    def test_filter_by_status(self, client, db):
        admin = _create_admin(db)
        _create_member_user(db, "active-member@test.com")
        client.cookies.update(_auth_cookie(admin))

        response = client.get("/api/v1/members/?status=active")
        assert response.status_code == 200
        items = response.json()["items"]
        for item in items:
            assert item["status"] == "active"

    def test_get_member(self, client, db):
        admin = _create_admin(db)
        _, member = _create_member_user(db, "get-member@test.com")
        client.cookies.update(_auth_cookie(admin))

        response = client.get(f"/api/v1/members/{member.id}")
        assert response.status_code == 200
        assert response.json()["id"] == member.id

    def test_update_member(self, client, db):
        admin = _create_admin(db)
        _, member = _create_member_user(db, "update-member@test.com")
        client.cookies.update(_auth_cookie(admin))

        response = client.put(
            f"/api/v1/members/{member.id}",
            json={"first_name": "Updated"},
        )
        assert response.status_code == 200
        assert response.json()["person"]["first_name"] == "Updated"

    def test_delete_member(self, client, db):
        admin = _create_admin(db)
        _, member = _create_member_user(db, "delete-member@test.com")
        client.cookies.update(_auth_cookie(admin))

        response = client.delete(f"/api/v1/members/{member.id}")
        assert response.status_code == 204

    def test_member_cannot_list(self, client, db):
        _, member = _create_member_user(db, "no-list@test.com")
        user = db.query(User).filter(User.id == member.user_id).first()
        client.cookies.update(_auth_cookie(user))

        response = client.get("/api/v1/members/")
        assert response.status_code == 403


class TestMemberStatus:
    def test_change_status_pending_to_active(self, client, db):
        admin = _create_admin(db)
        mt = _ensure_membership_type(db)
        client.cookies.update(_auth_cookie(admin))

        # Create a pending member
        create_resp = client.post(
            "/api/v1/members/",
            json={
                "first_name": "Pending",
                "last_name": "User",
                "membership_type_id": mt.id,
            },
        )
        member_id = create_resp.json()["id"]

        response = client.put(
            f"/api/v1/members/{member_id}/status",
            json={"status": "active"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "active"

    def test_invalid_status_transition(self, client, db):
        admin = _create_admin(db)
        mt = _ensure_membership_type(db)
        client.cookies.update(_auth_cookie(admin))

        # Create and activate member
        create_resp = client.post(
            "/api/v1/members/",
            json={
                "first_name": "Active",
                "last_name": "User",
                "membership_type_id": mt.id,
            },
        )
        member_id = create_resp.json()["id"]
        client.put(
            f"/api/v1/members/{member_id}/status",
            json={"status": "active"},
        )

        # Try invalid transition: active -> pending
        response = client.put(
            f"/api/v1/members/{member_id}/status",
            json={"status": "pending"},
        )
        assert response.status_code == 400


class TestMemberSelfService:
    def test_member_can_view_own_profile(self, client, db):
        user, member = _create_member_user(db, "self-view@test.com")
        client.cookies.update(_auth_cookie(user))

        response = client.get(f"/api/v1/members/{member.id}")
        assert response.status_code == 200

    def test_member_cannot_view_other(self, client, db):
        user, _ = _create_member_user(db, "self-only@test.com")
        _, other_member = _create_member_user(db, "other@test.com")
        client.cookies.update(_auth_cookie(user))

        response = client.get(f"/api/v1/members/{other_member.id}")
        assert response.status_code == 403

    def test_member_can_update_own(self, client, db):
        user, member = _create_member_user(db, "self-update@test.com")
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            f"/api/v1/members/{member.id}",
            json={"first_name": "MySelf"},
        )
        assert response.status_code == 200
        assert response.json()["person"]["first_name"] == "MySelf"
