"""Integration tests for activity cover image upload/delete endpoints."""

import io
from datetime import datetime, timedelta, timezone

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.activities.models import Activity
from app.domains.auth.models import User
from app.domains.persons.models import Person


def _create_user(db, role="admin", suffix=""):
    person = Person(first_name="Test", last_name="User", email=f"cover-{role}{suffix}@test.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=f"cover-{role}{suffix}@test.com",
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id, user.role)}


def _create_activity(db, **overrides):
    now = datetime.now(timezone.utc)
    defaults = {
        "name": "Cover Test Activity",
        "slug": f"cover-test-{id(overrides)}",
        "starts_at": now + timedelta(days=10),
        "ends_at": now + timedelta(days=11),
        "registration_starts_at": now - timedelta(days=1),
        "registration_ends_at": now + timedelta(days=9),
        "max_participants": 50,
        "status": "published",
        "is_active": True,
    }
    defaults.update(overrides)
    activity = Activity(**defaults)
    db.add(activity)
    db.flush()
    return activity


def _fake_image(ext="png", size_bytes=100):
    """Create a minimal fake image file for testing."""
    content = b"\x89PNG\r\n\x1a\n" + b"\x00" * max(0, size_bytes - 8)
    return ("test_image." + ext, io.BytesIO(content), "image/" + ext)


class TestCoverImageUpload:
    def test_upload_cover_image(self, client, db):
        admin = _create_user(db, "admin")
        activity = _create_activity(db)
        client.cookies.update(_auth_cookie(admin))

        filename, file_obj, content_type = _fake_image("png")
        response = client.post(
            f"/api/v1/activities/{activity.id}/cover-image/",
            files={"file": (filename, file_obj, content_type)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["image_url"] is not None
        assert f"/uploads/activities/{activity.id}/cover.png" in data["image_url"]

    def test_upload_replaces_existing(self, client, db):
        admin = _create_user(db, "admin", suffix="2")
        activity = _create_activity(db)
        client.cookies.update(_auth_cookie(admin))

        # Upload first image (png)
        filename, file_obj, content_type = _fake_image("png")
        client.post(
            f"/api/v1/activities/{activity.id}/cover-image/",
            files={"file": (filename, file_obj, content_type)},
        )

        # Upload second image (jpg) — should replace
        filename2, file_obj2, content_type2 = _fake_image("jpg")
        response = client.post(
            f"/api/v1/activities/{activity.id}/cover-image/",
            files={"file": (filename2, file_obj2, "image/jpeg")},
        )
        assert response.status_code == 200
        data = response.json()
        assert "cover.jpg" in data["image_url"]

    def test_upload_rejects_non_image(self, client, db):
        admin = _create_user(db, "admin", suffix="3")
        activity = _create_activity(db)
        client.cookies.update(_auth_cookie(admin))

        response = client.post(
            f"/api/v1/activities/{activity.id}/cover-image/",
            files={"file": ("doc.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        )
        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"]

    def test_upload_requires_admin(self, client, db):
        member = _create_user(db, "member", suffix="4")
        activity = _create_activity(db)
        client.cookies.update(_auth_cookie(member))

        filename, file_obj, content_type = _fake_image("png")
        response = client.post(
            f"/api/v1/activities/{activity.id}/cover-image/",
            files={"file": (filename, file_obj, content_type)},
        )
        assert response.status_code == 403

    def test_upload_404_for_nonexistent_activity(self, client, db):
        admin = _create_user(db, "admin", suffix="5")
        client.cookies.update(_auth_cookie(admin))

        filename, file_obj, content_type = _fake_image("png")
        response = client.post(
            "/api/v1/activities/99999/cover-image/",
            files={"file": (filename, file_obj, content_type)},
        )
        assert response.status_code == 404


class TestCoverImageDelete:
    def test_delete_cover_image(self, client, db):
        admin = _create_user(db, "admin", suffix="6")
        activity = _create_activity(db)
        client.cookies.update(_auth_cookie(admin))

        # Upload first
        filename, file_obj, content_type = _fake_image("png")
        client.post(
            f"/api/v1/activities/{activity.id}/cover-image/",
            files={"file": (filename, file_obj, content_type)},
        )

        # Delete
        response = client.delete(f"/api/v1/activities/{activity.id}/cover-image/")
        assert response.status_code == 204

        # Verify cleared
        get_resp = client.get(f"/api/v1/activities/{activity.id}")
        assert get_resp.json()["image_url"] is None

    def test_delete_when_no_image(self, client, db):
        admin = _create_user(db, "admin", suffix="7")
        activity = _create_activity(db)
        client.cookies.update(_auth_cookie(admin))

        response = client.delete(f"/api/v1/activities/{activity.id}/cover-image/")
        assert response.status_code == 404

    def test_delete_requires_admin(self, client, db):
        member = _create_user(db, "member", suffix="8")
        activity = _create_activity(db)
        client.cookies.update(_auth_cookie(member))

        response = client.delete(f"/api/v1/activities/{activity.id}/cover-image/")
        assert response.status_code == 403


class TestActivityListIncludesImageUrl:
    def test_list_response_includes_image_url(self, client, db):
        admin = _create_user(db, "admin", suffix="9")
        activity = _create_activity(db)
        client.cookies.update(_auth_cookie(admin))

        # Upload image
        filename, file_obj, content_type = _fake_image("png")
        client.post(
            f"/api/v1/activities/{activity.id}/cover-image/",
            files={"file": (filename, file_obj, content_type)},
        )

        # Check list response
        response = client.get("/api/v1/activities/")
        assert response.status_code == 200
        items = response.json()["items"]
        activity_item = next((a for a in items if a["id"] == activity.id), None)
        assert activity_item is not None
        assert activity_item["image_url"] is not None
        assert "cover.png" in activity_item["image_url"]
