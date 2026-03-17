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


class TestGuardianMinor:
    def test_create_minor_with_guardian(self, client, db):
        admin = _create_admin(db)
        mt = _ensure_membership_type(db)
        client.cookies.update(_auth_cookie(admin))

        # Create guardian person
        guardian = Person(first_name="Parent", last_name="García", email="parent@test.com")
        db.add(guardian)
        db.flush()

        response = client.post(
            "/api/v1/members/",
            json={
                "first_name": "Child",
                "last_name": "García",
                "date_of_birth": "2018-06-15",
                "membership_type_id": mt.id,
                "guardian_person_id": guardian.id,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["is_minor"] is True
        assert data["guardian"] is not None
        assert data["guardian"]["first_name"] == "Parent"
        assert data["guardian"]["last_name"] == "García"

    def test_create_adult_not_minor(self, client, db):
        admin = _create_admin(db)
        mt = _ensure_membership_type(db)
        client.cookies.update(_auth_cookie(admin))

        response = client.post(
            "/api/v1/members/",
            json={
                "first_name": "Adult",
                "last_name": "User",
                "date_of_birth": "1990-01-01",
                "membership_type_id": mt.id,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["is_minor"] is False
        assert data["guardian"] is None

    def test_create_without_dob_not_minor(self, client, db):
        admin = _create_admin(db)
        mt = _ensure_membership_type(db)
        client.cookies.update(_auth_cookie(admin))

        response = client.post(
            "/api/v1/members/",
            json={
                "first_name": "NoDob",
                "last_name": "User",
                "membership_type_id": mt.id,
            },
        )
        assert response.status_code == 201
        assert response.json()["is_minor"] is False

    def test_update_dob_recalculates_minor(self, client, db):
        admin = _create_admin(db)
        mt = _ensure_membership_type(db)
        client.cookies.update(_auth_cookie(admin))

        # Create adult member
        create_resp = client.post(
            "/api/v1/members/",
            json={
                "first_name": "Was",
                "last_name": "Adult",
                "date_of_birth": "1990-01-01",
                "membership_type_id": mt.id,
            },
        )
        member_id = create_resp.json()["id"]
        assert create_resp.json()["is_minor"] is False

        # Update DOB to make them a minor
        response = client.put(
            f"/api/v1/members/{member_id}",
            json={"date_of_birth": "2020-01-01"},
        )
        assert response.status_code == 200
        assert response.json()["is_minor"] is True

    def test_guardian_can_have_multiple_minors(self, client, db):
        admin = _create_admin(db)
        mt = _ensure_membership_type(db)
        client.cookies.update(_auth_cookie(admin))

        guardian = Person(first_name="Multi", last_name="Parent", email="multi-parent@test.com")
        db.add(guardian)
        db.flush()

        # Create first minor
        resp1 = client.post(
            "/api/v1/members/",
            json={
                "first_name": "Child1",
                "last_name": "Parent",
                "date_of_birth": "2016-03-01",
                "guardian_person_id": guardian.id,
                "membership_type_id": mt.id,
            },
        )
        assert resp1.status_code == 201
        assert resp1.json()["guardian"]["id"] == guardian.id

        # Create second minor with same guardian
        resp2 = client.post(
            "/api/v1/members/",
            json={
                "first_name": "Child2",
                "last_name": "Parent",
                "date_of_birth": "2019-07-15",
                "guardian_person_id": guardian.id,
                "membership_type_id": mt.id,
            },
        )
        assert resp2.status_code == 201
        assert resp2.json()["guardian"]["id"] == guardian.id
        assert resp1.json()["id"] != resp2.json()["id"]
