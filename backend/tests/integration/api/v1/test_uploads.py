"""Integration tests for the authenticated /uploads router.

The storage root used to be a StaticFiles mount, so every path under it —
including the encryption key and generated SEPA files — was downloadable with no
session at all. These tests pin the replacement: an allowlist of prefixes, an
ownership rule on each, and a 404 for everything else.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.members.models import Member
from app.domains.billing.models import SepaMandate
from app.domains.persons.models import Party, Person


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id)}


def _make_user(db, email, role="member", with_member=True):
    person = Person(first_name="Up", last_name="Loader", email=email)
    db.add(person)
    db.flush()
    user = User(
        party_id=person.party_id,
        email=email,
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    member = None
    if with_member:
        member = Member(party_id=person.party_id, status="active")
        db.add(member)
        db.flush()
    return user, person, member



# A pre-repoint mandate was filed under ``mandates/<member_id>/``, so a member
# whose ``party_id`` equals some other member's ``members.id`` lands on that
# other member's directory. Both sequences are low in a fresh database, so the
# collision is pinned explicitly here rather than left to chance.
COLLIDING_ID = 900_001


def _member_with_member_id(db, email, member_id):
    """A member whose ``members.id`` is pinned, so the pre-repoint storage path
    named after it can be constructed deterministically."""
    person = Person(first_name="Vic", last_name="Tim", email=email)
    db.add(person)
    db.flush()
    user = User(
        party_id=person.party_id,
        email=email,
        password_hash=hash_password("password123"),
        role="member",
        is_active=True,
    )
    db.add(user)
    member = Member(id=member_id, party_id=person.party_id, status="active")
    db.add(member)
    db.flush()
    return user, member


def _member_with_party_id(db, email, party_id):
    """A member whose ``party.id`` is pinned, to collide with another member's
    ``members.id``. ``_person_creates_its_party`` documents a wired
    ``party_id`` as a supported path."""
    db.add(Party(id=party_id, kind="person", display_name="Coll Ider"))
    db.flush()
    person = Person(party_id=party_id, first_name="Coll", last_name="Ider")
    db.add(person)
    db.flush()
    user = User(
        party_id=party_id,
        email=email,
        password_hash=hash_password("password123"),
        role="member",
        is_active=True,
    )
    db.add(user)
    db.add(Member(party_id=party_id, status="active"))
    db.flush()
    return user


def _mandate(db, party_id, reference, document_path):
    mandate = SepaMandate(
        party_id=party_id,
        mandate_reference=reference,
        creditor_id="ES12ZZZ12345678",
        debtor_name="Vic Tim",
        debtor_iban="ES9121000418450200051332",
        signed_at=date(2024, 3, 1),
        document_path=document_path,
    )
    db.add(mandate)
    db.flush()
    return mandate


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
        user, _, _ = _make_user(db, "rem@examplee6e3b1.com", role="admin")
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
        user, person, _ = _make_user(db, "own-photo@examplee6e3b1.com")
        storage(f"members/{person.party_id}/photo.png", b"\x89PNG")
        client.cookies.update(_auth_cookie(user))

        assert client.get(f"/uploads/members/{person.party_id}/photo.png").status_code == 200

    def test_locked_member_is_rejected_like_anonymous(self, client, db, storage):
        """`get_optional_user` used to filter on `is_active` alone, so a locked
        account kept downloading its files after every other route had shut it
        out (#254). It now resolves the token through the same query as
        `get_current_user`, and a locked account is simply not signed in.
        """
        user, person, _ = _make_user(db, "locked-photo@examplee6e3b1.com")
        user.is_locked = True
        db.flush()
        storage(f"members/{person.party_id}/photo.png", b"\x89PNG")
        client.cookies.update(_auth_cookie(user))

        assert client.get(f"/uploads/members/{person.party_id}/photo.png").status_code == 401

    def test_member_cannot_read_another_members_photo(self, client, db, storage):
        _, other_person, _ = _make_user(db, "victim-photo@examplee6e3b1.com")
        attacker, _, _ = _make_user(db, "attacker-photo@examplee6e3b1.com")
        storage(f"members/{other_person.party_id}/photo.png", b"\x89PNG")
        client.cookies.update(_auth_cookie(attacker))

        resp = client.get(f"/uploads/members/{other_person.party_id}/photo.png")
        assert resp.status_code == 404

    def test_staff_reads_any_photo(self, client, db, storage):
        _, other_person, _ = _make_user(db, "scanned@examplee6e3b1.com")
        staff, _, _ = _make_user(db, "staff-photo@examplee6e3b1.com", role="admin")
        storage(f"members/{other_person.party_id}/photo.png", b"\x89PNG")
        client.cookies.update(_auth_cookie(staff))

        assert client.get(f"/uploads/members/{other_person.party_id}/photo.png").status_code == 200


class TestMandates:
    def test_anonymous_is_rejected(self, client, storage):
        storage("mandates/1/MEM-0001-001.pdf", b"%PDF-1.4")

        assert client.get("/uploads/mandates/1/MEM-0001-001.pdf").status_code == 401

    def test_member_reads_own_mandate(self, client, db, storage):
        user, _, member = _make_user(db, "own-mandate@examplee6e3b1.com")
        path = f"mandates/{member.party_id}/MEM-0001-001.pdf"
        storage(path, b"%PDF-1.4")
        # The row is what authorises now, and reality always has one: the file
        # exists only because an upload wrote it and set document_path.
        _mandate(db, member.party_id, "MEM-0001-001", f"{settings.STORAGE_LOCAL_PATH}/{path}")
        client.cookies.update(_auth_cookie(user))

        resp = client.get(f"/uploads/{path}")
        assert resp.status_code == 200

    def test_member_cannot_read_another_members_mandate(self, client, db, storage):
        _, _, victim = _make_user(db, "victim-mandate@examplee6e3b1.com")
        attacker, _, _ = _make_user(db, "attacker-mandate@examplee6e3b1.com")
        path = f"mandates/{victim.party_id}/MEM-0002-001.pdf"
        storage(path, b"%PDF-1.4")
        _mandate(db, victim.party_id, "MEM-0002-001", f"{settings.STORAGE_LOCAL_PATH}/{path}")
        client.cookies.update(_auth_cookie(attacker))

        resp = client.get(f"/uploads/{path}")
        assert resp.status_code == 404


class TestMandatesUploadedBeforeTheRepoint:
    """An upgraded install's signed mandates sit at ``mandates/<member_id>/``.

    The old ``storage_dir`` read ``mandate.member_id`` and ``document_path``
    kept whatever path was written, so no migration moved either. The guard
    must therefore authorise against the mandate row: the directory name now
    names a *party*, and ``members.id`` and ``party.id`` are independent
    sequences that only coincide by accident.

    The upload is a scan of signed paper (jpg and png are accepted), so these
    files cannot be regenerated and must not be moved or deleted to make the
    path honest.
    """

    def test_owner_reads_their_pre_repoint_mandate(self, client, db, storage):
        owner, member = _member_with_member_id(
            db, "pre-own@examplee6e3b1.com", COLLIDING_ID
        )
        path = f"mandates/{member.id}/MEM-0042-001.pdf"
        storage(path, b"%PDF-1.4")
        _mandate(db, member.party_id, "MEM-0042-001", str(settings.STORAGE_LOCAL_PATH) + "/" + path)
        client.cookies.update(_auth_cookie(owner))

        resp = client.get(f"/uploads/{path}")
        assert resp.status_code == 200

    def test_member_whose_party_id_matches_the_directory_is_refused(
        self, client, db, storage
    ):
        """The exposure. The directory is named after the owner's ``members.id``;
        an unrelated member whose ``party_id`` happens to equal that number
        passes a guard that compares the path segment, and receives a signed
        mandate carrying somebody else's IBAN and signature."""
        _, member = _member_with_member_id(
            db, "pre-victim@examplee6e3b1.com", COLLIDING_ID
        )
        attacker = _member_with_party_id(
            db, "pre-attacker@examplee6e3b1.com", COLLIDING_ID
        )
        path = f"mandates/{member.id}/MEM-0043-001.pdf"
        storage(path, b"%PDF-1.4")
        _mandate(db, member.party_id, "MEM-0043-001", str(settings.STORAGE_LOCAL_PATH) + "/" + path)
        client.cookies.update(_auth_cookie(attacker))

        resp = client.get(f"/uploads/{path}")
        assert resp.status_code == 404

    def test_billing_staff_reads_a_pre_repoint_mandate(self, client, db, storage):
        _, member = _member_with_member_id(
            db, "pre-staff-target@examplee6e3b1.com", COLLIDING_ID
        )
        staff, _, _ = _make_user(db, "pre-staff@examplee6e3b1.com", role="admin")
        path = f"mandates/{member.id}/MEM-0044-001.pdf"
        storage(path, b"%PDF-1.4")
        _mandate(db, member.party_id, "MEM-0044-001", str(settings.STORAGE_LOCAL_PATH) + "/" + path)
        client.cookies.update(_auth_cookie(staff))

        resp = client.get(f"/uploads/{path}")
        assert resp.status_code == 200

    def test_a_path_with_no_mandate_row_is_not_served(self, client, db, storage):
        """A file on the volume that no mandate row points at has no owner to
        check, so it stays unreachable rather than falling back to the path."""
        user, _, member = _make_user(db, "pre-orphan@examplee6e3b1.com")
        path = f"mandates/{member.party_id}/MEM-0045-001.pdf"
        storage(path, b"%PDF-1.4")
        client.cookies.update(_auth_cookie(user))

        resp = client.get(f"/uploads/{path}")
        assert resp.status_code == 404


class TestExecutableUploadsAreNeutralised:
    def test_html_is_forced_to_download(self, client, db, storage):
        """C7 lets an attacker store .html under registrations/. It must not come
        back as a renderable page on the app's own origin."""
        user, _, member = _make_user(db, "html-upload@examplee6e3b1.com")
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
        registration = Registration(activity_id=activity.id, party_id=member.party_id)
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
