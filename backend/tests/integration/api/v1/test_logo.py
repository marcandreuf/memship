"""Integration tests for organization logo upload/delete endpoints."""

import io

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


def _create_user(db, role="super_admin", suffix="logo"):
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
    existing = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not existing:
        org = OrganizationSettings(
            id=1, name="Test Org", locale="es", timezone="Europe/Madrid",
            currency="EUR", date_format="DD/MM/YYYY",
        )
        db.add(org)
        db.flush()
    return db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()


def _make_image_file(ext="png", size=100):
    """Create a minimal fake image file for testing."""
    content = b"\x89PNG\r\n\x1a\n" + b"\x00" * size  # PNG magic bytes + padding
    return ("test." + ext, io.BytesIO(content), "image/" + ext)


class TestLogoUpload:
    def test_upload_logo(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "super_admin", "logo-up")
        client.cookies.update(_auth_cookie(user))

        filename, file_obj, content_type = _make_image_file("png")
        response = client.post(
            "/api/v1/settings/logo/",
            files={"file": (filename, file_obj, content_type)},
        )
        assert response.status_code == 200
        data = response.json()
        assert "logo_url" in data
        assert data["logo_url"].startswith("/uploads/org/logo.")

    def test_upload_replaces_existing(self, client, db):
        org = _ensure_org_settings(db)
        org.logo_url = "/uploads/org/logo.png"
        db.flush()
        user = _create_user(db, "super_admin", "logo-replace")
        client.cookies.update(_auth_cookie(user))

        filename, file_obj, content_type = _make_image_file("jpeg")
        response = client.post(
            "/api/v1/settings/logo/",
            files={"file": (filename, file_obj, "image/jpeg")},
        )
        assert response.status_code == 200
        assert response.json()["logo_url"].endswith(".jpeg")

    def test_upload_rejects_non_image(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "super_admin", "logo-noimg")
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            "/api/v1/settings/logo/",
            files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        )
        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"].lower()

    def test_upload_requires_super_admin(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "admin", "logo-rbac")
        client.cookies.update(_auth_cookie(user))

        filename, file_obj, content_type = _make_image_file()
        response = client.post(
            "/api/v1/settings/logo/",
            files={"file": (filename, file_obj, content_type)},
        )
        assert response.status_code == 403

    def test_delete_logo(self, client, db):
        org = _ensure_org_settings(db)
        org.logo_url = "/uploads/org/logo.png"
        db.flush()
        user = _create_user(db, "super_admin", "logo-del")
        client.cookies.update(_auth_cookie(user))

        response = client.delete("/api/v1/settings/logo/")
        assert response.status_code == 204

        db.refresh(org)
        assert org.logo_url is None

    def test_delete_logo_404_when_none(self, client, db):
        org = _ensure_org_settings(db)
        org.logo_url = None
        db.flush()
        user = _create_user(db, "super_admin", "logo-del404")
        client.cookies.update(_auth_cookie(user))

        response = client.delete("/api/v1/settings/logo/")
        assert response.status_code == 404

    def test_logo_visible_in_settings_response(self, client, db):
        org = _ensure_org_settings(db)
        org.logo_url = "/uploads/org/logo.png"
        db.flush()
        user = _create_user(db, "member", "logo-get")
        client.cookies.update(_auth_cookie(user))

        response = client.get("/api/v1/settings/")
        assert response.status_code == 200
        assert response.json()["logo_url"] == "/uploads/org/logo.png"
