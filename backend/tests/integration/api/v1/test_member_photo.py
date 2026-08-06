"""Integration tests for member self-service profile photo upload/delete."""

import io

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.persons.models import Person


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id)}


def _create_member_user(db, email="photo-member@test.com"):
    person = Person(first_name="Photo", last_name="Tester", email=email)
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
    return user, person


def _fake_image(ext="png"):
    content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    return ("me." + ext, io.BytesIO(content), "image/" + ext)


class TestMemberPhotoUpload:
    def test_member_uploads_own_photo(self, client, db):
        user, person = _create_member_user(db)
        client.cookies.update(_auth_cookie(user))

        filename, file_obj, content_type = _fake_image("png")
        resp = client.post(
            "/api/v1/members/me/photo/",
            files={"file": (filename, file_obj, content_type)},
        )
        assert resp.status_code == 200
        photo_url = resp.json()["photo_url"]
        assert photo_url == f"/uploads/members/{person.id}/photo.png"

        db.refresh(person)
        assert person.photo_url == photo_url

    def test_rejects_non_image_extension(self, client, db):
        user, _ = _create_member_user(db, email="photo-bad@test.com")
        client.cookies.update(_auth_cookie(user))

        resp = client.post(
            "/api/v1/members/me/photo/",
            files={"file": ("resume.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        )
        assert resp.status_code == 400

    def test_rejects_non_image_content_type(self, client, db):
        user, _ = _create_member_user(db, email="photo-ct@test.com")
        client.cookies.update(_auth_cookie(user))

        resp = client.post(
            "/api/v1/members/me/photo/",
            files={"file": ("me.png", io.BytesIO(b"nope"), "text/plain")},
        )
        assert resp.status_code == 400

    def test_delete_photo(self, client, db):
        user, person = _create_member_user(db, email="photo-del@test.com")
        client.cookies.update(_auth_cookie(user))

        filename, file_obj, content_type = _fake_image("png")
        client.post(
            "/api/v1/members/me/photo/",
            files={"file": (filename, file_obj, content_type)},
        )

        resp = client.delete("/api/v1/members/me/photo/")
        assert resp.status_code == 204

        db.refresh(person)
        assert person.photo_url is None

    def test_delete_when_no_photo_404(self, client, db):
        user, _ = _create_member_user(db, email="photo-none@test.com")
        client.cookies.update(_auth_cookie(user))

        resp = client.delete("/api/v1/members/me/photo/")
        assert resp.status_code == 404

    def test_upload_requires_auth(self, client, db):
        filename, file_obj, content_type = _fake_image("png")
        resp = client.post(
            "/api/v1/members/me/photo/",
            files={"file": (filename, file_obj, content_type)},
        )
        assert resp.status_code == 401
