"""Integration tests for member self-service profile photo upload/delete."""

import io

import pytest

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.persons.models import Person


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id)}


def _create_member_user(db, email="photo-member@examplee6e3b1.com"):
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

    def test_a_failed_commit_leaves_the_previous_photo_in_place(
        self, client, db, tmp_path, monkeypatch
    ):
        """The old file used to be deleted before the row was committed, so a
        commit that failed left the row pointing at nothing (#259). Now the
        row is committed first and the old file survives the failure."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "STORAGE_LOCAL_PATH", str(tmp_path))
        user, person = _create_member_user(db, email="photo-keep@examplee6e3b1.com")
        client.cookies.update(_auth_cookie(user))

        filename, file_obj, content_type = _fake_image("jpg")
        assert client.post(
            "/api/v1/members/me/photo/",
            files={"file": (filename, file_obj, content_type)},
        ).status_code == 200
        photo_dir = tmp_path / "members" / str(person.id)
        old_bytes = (photo_dir / "photo.jpg").read_bytes()

        def failing_commit():
            raise RuntimeError("connection lost")

        monkeypatch.setattr(db, "commit", failing_commit)
        filename, file_obj, content_type = _fake_image("png")
        with pytest.raises(RuntimeError, match="connection lost"):
            client.post(
                "/api/v1/members/me/photo/",
                files={"file": (filename, file_obj, content_type)},
            )

        assert sorted(p.name for p in photo_dir.iterdir()) == ["photo.jpg"]
        assert (photo_dir / "photo.jpg").read_bytes() == old_bytes

    def test_rejects_non_image_extension(self, client, db):
        user, _ = _create_member_user(db, email="photo-bad@examplee6e3b1.com")
        client.cookies.update(_auth_cookie(user))

        resp = client.post(
            "/api/v1/members/me/photo/",
            files={"file": ("resume.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        )
        assert resp.status_code == 400

    def test_rejects_non_image_content_type(self, client, db):
        user, _ = _create_member_user(db, email="photo-ct@examplee6e3b1.com")
        client.cookies.update(_auth_cookie(user))

        resp = client.post(
            "/api/v1/members/me/photo/",
            files={"file": ("me.png", io.BytesIO(b"nope"), "text/plain")},
        )
        assert resp.status_code == 400

    def test_delete_photo(self, client, db):
        user, person = _create_member_user(db, email="photo-del@examplee6e3b1.com")
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
        user, _ = _create_member_user(db, email="photo-none@examplee6e3b1.com")
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
