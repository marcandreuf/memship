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
        _create_test_user(db, email="login@examplee6e3b1.com", password="password123")

        response = client.post(
            "/api/v1/auth/login",
            json={"email": "login@examplee6e3b1.com", "password": "password123"},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Login successful"
        assert "access_token" in response.cookies

    def test_login_wrong_password(self, client, db):
        _create_test_user(db, email="wrong@examplee6e3b1.com", password="password123")

        response = client.post(
            "/api/v1/auth/login",
            json={"email": "wrong@examplee6e3b1.com", "password": "wrongpassword"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid email or password"

    def test_login_nonexistent_email(self, client):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@examplee6e3b1.com", "password": "password123"},
        )
        assert response.status_code == 401

    def test_login_locked_account(self, client, db):
        user = _create_test_user(db, email="locked@examplee6e3b1.com", password="password123")
        user.is_locked = True
        db.flush()

        response = client.post(
            "/api/v1/auth/login",
            json={"email": "locked@examplee6e3b1.com", "password": "password123"},
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
                "email": "new@examplee6e3b1.com",
                "password": "password123",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "new@examplee6e3b1.com"
        assert data["member_status"] == "pending"
        assert data["requires_approval"] is True
        # Registration must NOT log the user in — approval is still pending.
        assert "access_token" not in response.cookies

        member = (
            db.query(Member)
            .join(Person, Member.person_id == Person.id)
            .filter(Person.email == "new@examplee6e3b1.com")
            .first()
        )
        # The member number is allocated on approval, not at sign-up.
        assert member.member_number is None

    def test_register_duplicate_email(self, client, db):
        _create_test_user(db, email="dupe@examplee6e3b1.com")

        response = client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "Dup",
                "last_name": "User",
                "email": "dupe@examplee6e3b1.com",
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
                "email": "short@examplee6e3b1.com",
                "password": "1234567",
            },
        )
        assert response.status_code == 422


class TestMe:
    def test_me_authenticated(self, client, db):
        _create_test_user(db, email="me@examplee6e3b1.com", password="password123")

        # Login first
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "me@examplee6e3b1.com", "password": "password123"},
        )
        assert login_response.status_code == 200

        # Access /me with the cookie
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "me@examplee6e3b1.com"
        assert data["first_name"] == "Test"

    def test_me_unauthenticated(self, client):
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401


class TestPasswordReset:
    def test_password_reset_flow(self, client, db):
        _create_test_user(db, email="reset@examplee6e3b1.com", password="oldpassword1")

        # Request reset
        response = client.post(
            "/api/v1/auth/password-reset-request",
            json={"email": "reset@examplee6e3b1.com"},
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
            json={"email": "reset@examplee6e3b1.com", "password": "newpassword1"},
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
            json={"email": "nobody@examplee6e3b1.com"},
        )
        assert response.status_code == 200
        # Should not reveal whether email exists
        assert response.json()["reset_token"] is None

    def test_super_admin_cannot_request_a_reset(self, client, db):
        """Email must not stand in for the account that owns the instance.

        The response has to be the same one an unknown address gets, or the
        endpoint turns into a way to ask which accounts are super admins.
        """
        _create_test_user(db, email="owner@examplee6e3b1.com", role="super_admin")

        response = client.post(
            "/api/v1/auth/password-reset-request",
            json={"email": "owner@examplee6e3b1.com"},
        )

        assert response.status_code == 200
        assert response.json()["reset_token"] is None

    def test_super_admin_token_issued_before_the_rule_is_refused(self, client, db):
        """A token already in flight when this shipped must stop working too."""
        from datetime import datetime, timedelta, timezone

        user = _create_test_user(db, email="owner2@examplee6e3b1.com", role="super_admin")
        user.reset_token = "still-inside-its-hour"
        user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        db.flush()

        response = client.post(
            "/api/v1/auth/password-reset",
            json={"token": "still-inside-its-hour", "new_password": "newpassword1"},
        )

        assert response.status_code == 400


class TestLogout:
    def test_logout(self, client):
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 200
        assert response.json()["message"] == "Logged out"
