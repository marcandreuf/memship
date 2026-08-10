"""Integration tests for the authenticated /uploads router.

The storage root used to be a StaticFiles mount, so every path under it —
including the encryption key and generated SEPA files — was downloadable with no
session at all. These tests pin the replacement: an allowlist of prefixes, an
ownership rule on each, and a 404 for everything else.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.members.models import Member
from app.domains.persons.models import Person


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id)}


def _make_user(db, email, role="member", with_member=True):
    person = Person(first_name="Up", last_name="Loader", email=email)
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=email,
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    member = None
    if with_member:
        member = Member(person_id=person.id, user_id=user.id, status="active")
        db.add(member)
        db.flush()
    return user, person, member


@pytest.fixture
def storage(tmp_path, monkeypatch):
    """Point the storage root at a temp dir and hand back a file writer."""
    monkeypatch.setattr(settings, "STORAGE_LOCAL_PATH", str(tmp_path))

    def write(relative: str, content: bytes = b"payload") -> None:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    return write


class TestSecretsAreNotServed:
    def test_encryption_key_is_not_downloadable(self, client, storage):
        storage("secret.key", b"a-fernet-key")

        assert client.get("/uploads/secret.key").status_code == 404

    def test_remittance_xml_is_not_downloadable(self, client, db, storage):
        """The bank file has its own authenticated endpoint; the predictable
        filename must not be a second, anonymous way in."""
        storage("remittances/2026/REM-2026-0001.xml", b"<Document/>")
        user, _, _ = _make_user(db, "rem@test.com", role="admin")
        client.cookies.update(_auth_cookie(user))

        resp = client.get("/uploads/remittances/2026/REM-2026-0001.xml")
        assert resp.status_code == 404

    def test_traversal_out_of_the_storage_root_is_refused(self, client, storage):
        assert client.get("/uploads/org/../../etc/passwd").status_code == 404


class TestPublicPrefix:
    def test_org_logo_is_served_without_a_session(self, client, storage):
        storage("org/logo.png", b"\x89PNG\r\n\x1a\n")

        resp = client.get("/uploads/org/logo.png")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("image/png")
        assert resp.headers["x-content-type-options"] == "nosniff"


class TestMemberPhotos:
    def test_anonymous_is_rejected(self, client, storage):
        storage("members/1/photo.png", b"\x89PNG")

        assert client.get("/uploads/members/1/photo.png").status_code == 401

    def test_member_reads_own_photo(self, client, db, storage):
        user, person, _ = _make_user(db, "own-photo@test.com")
        storage(f"members/{person.id}/photo.png", b"\x89PNG")
        client.cookies.update(_auth_cookie(user))

        assert client.get(f"/uploads/members/{person.id}/photo.png").status_code == 200

    def test_member_cannot_read_another_members_photo(self, client, db, storage):
        _, other_person, _ = _make_user(db, "victim-photo@test.com")
        attacker, _, _ = _make_user(db, "attacker-photo@test.com")
        storage(f"members/{other_person.id}/photo.png", b"\x89PNG")
        client.cookies.update(_auth_cookie(attacker))

        resp = client.get(f"/uploads/members/{other_person.id}/photo.png")
        assert resp.status_code == 404

    def test_staff_reads_any_photo(self, client, db, storage):
        _, other_person, _ = _make_user(db, "scanned@test.com")
        staff, _, _ = _make_user(db, "staff-photo@test.com", role="admin")
        storage(f"members/{other_person.id}/photo.png", b"\x89PNG")
        client.cookies.update(_auth_cookie(staff))

        assert client.get(f"/uploads/members/{other_person.id}/photo.png").status_code == 200


class TestMandates:
    def test_anonymous_is_rejected(self, client, storage):
        storage("mandates/1/MEM-0001-001.pdf", b"%PDF-1.4")

        assert client.get("/uploads/mandates/1/MEM-0001-001.pdf").status_code == 401

    def test_member_reads_own_mandate(self, client, db, storage):
        user, _, member = _make_user(db, "own-mandate@test.com")
        storage(f"mandates/{member.id}/MEM-0001-001.pdf", b"%PDF-1.4")
        client.cookies.update(_auth_cookie(user))

        resp = client.get(f"/uploads/mandates/{member.id}/MEM-0001-001.pdf")
        assert resp.status_code == 200

    def test_member_cannot_read_another_members_mandate(self, client, db, storage):
        _, _, victim = _make_user(db, "victim-mandate@test.com")
        attacker, _, _ = _make_user(db, "attacker-mandate@test.com")
        storage(f"mandates/{victim.id}/MEM-0002-001.pdf", b"%PDF-1.4")
        client.cookies.update(_auth_cookie(attacker))

        resp = client.get(f"/uploads/mandates/{victim.id}/MEM-0002-001.pdf")
        assert resp.status_code == 404


class TestExecutableUploadsAreNeutralised:
    def test_html_is_forced_to_download(self, client, db, storage):
        """C7 lets an attacker store .html under registrations/. It must not come
        back as a renderable page on the app's own origin."""
        user, _, member = _make_user(db, "html-upload@test.com")
        from app.domains.activities.models import Activity, Registration

        now = datetime.now(timezone.utc)
        activity = Activity(
            name="Camp",
            slug="camp-uploads-test",
            status="published",
            starts_at=now + timedelta(days=10),
            ends_at=now + timedelta(days=11),
            registration_starts_at=now - timedelta(days=1),
            registration_ends_at=now + timedelta(days=9),
            max_participants=50,
        )
        db.add(activity)
        db.flush()
        registration = Registration(activity_id=activity.id, member_id=member.id)
        db.add(registration)
        db.flush()

        storage(f"registrations/{registration.id}/evil.html", b"<script>alert(1)</script>")
        client.cookies.update(_auth_cookie(user))

        resp = client.get(f"/uploads/registrations/{registration.id}/evil.html")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/octet-stream")
        assert resp.headers["content-disposition"].startswith("attachment")
        assert resp.headers["x-content-type-options"] == "nosniff"

    def test_svg_logo_keeps_its_type_but_never_renders_as_a_page(self, client, storage):
        storage("org/logo.svg", b"<svg xmlns='http://www.w3.org/2000/svg'/>")

        resp = client.get("/uploads/org/logo.svg")
        assert resp.status_code == 200
        # <img> ignores Content-Disposition, so the logo still renders; direct
        # navigation downloads it instead of running its script.
        assert resp.headers["content-type"].startswith("image/svg+xml")
        assert resp.headers["content-disposition"].startswith("attachment")
