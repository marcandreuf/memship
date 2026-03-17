"""Integration tests for auth endpoints."""

from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.members.models import Member, MembershipType
from app.domains.persons.models import Person


def _create_test_user(db, email="test@example.com", password="password123", role="member"):
    """Helper to create a user with person and member for tests."""
    person = Person(first_name="Test", last_name="User", email=email)
    db.add(person)
    db.flush()

    user = User(
        person_id=person.id,
        email=email,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
        email_verified=True,
    )
    db.add(user)
    db.flush()

    mt = db.query(MembershipType).first()
    if not mt:
        mt = MembershipType(name="Test", slug="test", is_active=True)
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

    return user


class TestLogin:
    def test_login_success(self, client, db):
        _create_test_user(db, email="login@test.com", password="password123")

        response = client.post(
            "/api/v1/auth/login",
            json={"email": "login@test.com", "password": "password123"},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Login successful"
        assert "access_token" in response.cookies

    def test_login_wrong_password(self, client, db):
        _create_test_user(db, email="wrong@test.com", password="password123")

        response = client.post(
            "/api/v1/auth/login",
            json={"email": "wrong@test.com", "password": "wrongpassword"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"

    def test_login_nonexistent_email(self, client):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@test.com", "password": "password123"},
        )
        assert response.status_code == 401

    def test_login_locked_account(self, client, db):
        user = _create_test_user(db, email="locked@test.com", password="password123")
        user.is_locked = True
        db.flush()

        response = client.post(
            "/api/v1/auth/login",
            json={"email": "locked@test.com", "password": "password123"},
        )
        assert response.status_code == 403
        assert "locked" in response.json()["detail"].lower()


class TestRegister:
    def test_register_success(self, client, db):
        # Ensure a default membership type exists
        mt = db.query(MembershipType).first()
        if not mt:
            mt = MembershipType(name="General", slug="general", is_active=True)
            db.add(mt)
            db.flush()

        response = client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "New",
                "last_name": "User",
                "email": "new@test.com",
                "password": "password123",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "new@test.com"
        assert data["role"] == "member"
        assert data["first_name"] == "New"
        assert data["member_number"] is not None
        assert "access_token" in response.cookies

    def test_register_duplicate_email(self, client, db):
        _create_test_user(db, email="dupe@test.com")

        response = client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "Dup",
                "last_name": "User",
                "email": "dupe@test.com",
                "password": "password123",
            },
        )
        assert response.status_code == 409

    def test_register_short_password(self, client):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "Short",
                "last_name": "Pass",
                "email": "short@test.com",
                "password": "1234567",
            },
        )
        assert response.status_code == 422


class TestMe:
    def test_me_authenticated(self, client, db):
        _create_test_user(db, email="me@test.com", password="password123")

        # Login first
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "me@test.com", "password": "password123"},
        )
        assert login_response.status_code == 200

        # Access /me with the cookie
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "me@test.com"
        assert data["first_name"] == "Test"

    def test_me_unauthenticated(self, client):
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401


class TestPasswordReset:
    def test_password_reset_flow(self, client, db):
        _create_test_user(db, email="reset@test.com", password="oldpassword1")

        # Request reset
        response = client.post(
            "/api/v1/auth/password-reset-request",
            json={"email": "reset@test.com"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["reset_token"] is not None
        token = data["reset_token"]

        # Reset password
        response = client.post(
            "/api/v1/auth/password-reset",
            json={"token": token, "new_password": "newpassword1"},
        )
        assert response.status_code == 200

        # Login with new password
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "reset@test.com", "password": "newpassword1"},
        )
        assert response.status_code == 200

    def test_password_reset_invalid_token(self, client):
        response = client.post(
            "/api/v1/auth/password-reset",
            json={"token": "invalid-token", "new_password": "newpassword1"},
        )
        assert response.status_code == 400

    def test_password_reset_nonexistent_email(self, client):
        response = client.post(
            "/api/v1/auth/password-reset-request",
            json={"email": "nobody@test.com"},
        )
        assert response.status_code == 200
        # Should not reveal whether email exists
        assert response.json()["reset_token"] is None


class TestLogout:
    def test_logout(self, client):
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 200
        assert response.json()["message"] == "Logged out"
