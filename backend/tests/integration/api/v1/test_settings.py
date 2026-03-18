"""Integration tests for organization settings endpoints."""

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


def _create_user(db, role="super_admin", suffix="settings"):
    person = Person(first_name="Test", last_name="User", email=f"{suffix}-{role}@test.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=f"{suffix}-{role}@test.com",
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id, user.role)}


def _ensure_org_settings(db):
    """Ensure organization_settings record exists."""
    existing = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not existing:
        org = OrganizationSettings(
            id=1,
            name="Test Organization",
            locale="es",
            timezone="Europe/Madrid",
            currency="EUR",
            date_format="DD/MM/YYYY",
        )
        db.add(org)
        db.flush()
    return db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()


class TestGetSettings:
    def test_get_settings_authenticated(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "member", "get-set")
        client.cookies.update(_auth_cookie(user))

        response = client.get("/api/v1/settings/")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["name"] == "Test Organization"
        assert data["locale"] == "es"

    def test_get_settings_unauthenticated(self, client):
        response = client.get("/api/v1/settings/")
        assert response.status_code in (401, 403)


class TestUpdateSettings:
    def test_update_settings_super_admin(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "super_admin", "upd-sa")
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            "/api/v1/settings/",
            json={"name": "Updated Club", "locale": "ca", "brand_color": "#3B82F6"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Club"
        assert data["locale"] == "ca"
        assert data["brand_color"] == "#3B82F6"

    def test_update_settings_admin_forbidden(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "admin", "upd-adm")
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            "/api/v1/settings/",
            json={"name": "Blocked"},
        )
        assert response.status_code == 403

    def test_update_settings_member_forbidden(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "member", "upd-mem")
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            "/api/v1/settings/",
            json={"name": "Blocked"},
        )
        assert response.status_code == 403

    def test_update_settings_partial(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "super_admin", "upd-partial")
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            "/api/v1/settings/",
            json={"phone": "+34 600 123 456"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["phone"] == "+34 600 123 456"
        assert data["name"] == "Test Organization"  # unchanged

    def test_update_invalid_locale(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "super_admin", "upd-invloc")
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            "/api/v1/settings/",
            json={"locale": "fr"},
        )
        assert response.status_code == 422

    def test_update_invalid_brand_color(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "super_admin", "upd-invclr")
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            "/api/v1/settings/",
            json={"brand_color": "not-a-color"},
        )
        assert response.status_code == 422
