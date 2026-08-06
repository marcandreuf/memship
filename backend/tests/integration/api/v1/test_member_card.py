"""Integration tests for the digital member card + QR check-in (v0.7.0)."""

from app.core.security.card_token import sign_card_token, verify_card_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


def _auth_cookie(user):
    from app.core.security.jwt import create_access_token

    return {"access_token": create_access_token(user.id)}


def _ensure_org(db, *, member_card=True, prefix="", padding=4, next_num=1):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(
            id=1,
            name="Test Club",
            locale="es",
            timezone="Europe/Madrid",
            currency="EUR",
            date_format="DD/MM/YYYY",
            brand_color="#0083ad",
        )
        db.add(org)
    org.features = {"member_card": member_card} if member_card else {}
    org.member_number_prefix = prefix
    org.member_number_padding = padding
    org.member_number_next = next_num
    db.flush()
    return org


def _create_admin(db, email="admin-card@test.com"):
    person = Person(first_name="Admin", last_name="Card", email=email)
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=email,
        password_hash=hash_password("password123"),
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _create_member_user(db, email="member-card@test.com", status="active", number="SCB-0001"):
    person = Person(first_name="Mika", last_name="Roig", email=email)
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
        member_number=number,
        status=status,
    )
    db.add(member)
    db.flush()
    return user, member


# --- Card token unit behaviour ---


class TestCardToken:
    def test_sign_verify_roundtrip(self):
        token = sign_card_token(123)
        assert token.startswith("123.")
        assert verify_card_token(token) == 123

    def test_tampered_or_malformed_rejected(self):
        token = sign_card_token(7)
        tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
        assert verify_card_token(tampered) is None       # bad signature
        assert verify_card_token("7.deadbeef") is None    # wrong signature
        assert verify_card_token("notanumber.abc") is None  # non-int id
        assert verify_card_token("garbage") is None        # no separator
        assert verify_card_token("") is None               # empty
        assert verify_card_token("0.abc") is None          # non-positive id


# --- Member card endpoints ---


class TestMemberCard:
    def test_get_my_card_fields(self, client, db):
        _ensure_org(db, prefix="SCB-")
        user, member = _create_member_user(db)
        client.cookies.update(_auth_cookie(user))

        resp = client.get("/api/v1/me/card")
        assert resp.status_code == 200
        data = resp.json()
        assert data["member_id"] == member.id
        assert data["full_name"] == "Mika Roig"
        assert data["member_number"] == "SCB-0001"
        assert data["status"] == "active"
        assert data["organization"]["name"] == "Test Club"
        assert data["organization"]["brand_color"] == "#0083ad"
        assert verify_card_token(data["token"]) == member.id

    def test_non_member_gets_403(self, client, db):
        _ensure_org(db)
        admin = _create_admin(db)  # admin user with no Member row
        client.cookies.update(_auth_cookie(admin))

        resp = client.get("/api/v1/me/card")
        assert resp.status_code == 403

    def test_qr_svg_returns_svg(self, client, db):
        _ensure_org(db)
        user, _ = _create_member_user(db)
        client.cookies.update(_auth_cookie(user))

        resp = client.get("/api/v1/me/card/qr.svg")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("image/svg+xml")
        assert b"<svg" in resp.content

    def test_pdf_returns_application_pdf(self, client, db):
        _ensure_org(db)
        user, _ = _create_member_user(db)
        client.cookies.update(_auth_cookie(user))

        resp = client.get("/api/v1/me/card/pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:5] == b"%PDF-"

    def test_card_404_when_module_off(self, client, db):
        _ensure_org(db, member_card=False)
        user, _ = _create_member_user(db)
        client.cookies.update(_auth_cookie(user))

        assert client.get("/api/v1/me/card").status_code == 404
        assert client.get("/api/v1/me/card/qr.svg").status_code == 404


# --- Admin scan ---


class TestScan:
    def test_scan_valid_returns_member_status(self, client, db):
        _ensure_org(db)
        admin = _create_admin(db)
        _user, member = _create_member_user(db)
        token = sign_card_token(member.id)
        client.cookies.update(_auth_cookie(admin))

        resp = client.post("/api/v1/card/scan", json={"token": token})
        assert resp.status_code == 200
        data = resp.json()
        assert data["member_id"] == member.id
        assert data["full_name"] == "Mika Roig"
        assert data["member_number"] == "SCB-0001"
        assert data["status"] == "active"

    def test_scan_reflects_live_suspension(self, client, db):
        _ensure_org(db)
        admin = _create_admin(db)
        _user, member = _create_member_user(db)
        token = sign_card_token(member.id)
        client.cookies.update(_auth_cookie(admin))

        # Card was "issued" while active; suspend after the fact.
        member.status = "suspended"
        db.flush()

        resp = client.post("/api/v1/card/scan", json={"token": token})
        assert resp.status_code == 200
        assert resp.json()["status"] == "suspended"

    def test_scan_invalid_signature_400(self, client, db):
        _ensure_org(db)
        admin = _create_admin(db)
        _create_member_user(db)
        client.cookies.update(_auth_cookie(admin))

        resp = client.post("/api/v1/card/scan", json={"token": "1.deadbeef"})
        assert resp.status_code == 400

    def test_scan_unknown_member_404(self, client, db):
        _ensure_org(db)
        admin = _create_admin(db)
        client.cookies.update(_auth_cookie(admin))

        token = sign_card_token(999999)  # correctly signed, no such member
        resp = client.post("/api/v1/card/scan", json={"token": token})
        assert resp.status_code == 404

    def test_member_cannot_scan(self, client, db):
        _ensure_org(db)
        user, member = _create_member_user(db)
        client.cookies.update(_auth_cookie(user))

        resp = client.post(
            "/api/v1/card/scan", json={"token": sign_card_token(member.id)}
        )
        assert resp.status_code == 403

    def test_scan_404_when_module_off(self, client, db):
        _ensure_org(db, member_card=False)
        admin = _create_admin(db)
        _user, member = _create_member_user(db)
        client.cookies.update(_auth_cookie(admin))

        resp = client.post(
            "/api/v1/card/scan", json={"token": sign_card_token(member.id)}
        )
        assert resp.status_code == 404


# --- Admin: view/print any member's card ---


class TestAdminMemberCard:
    def test_admin_gets_member_card(self, client, db):
        _ensure_org(db)
        admin = _create_admin(db)
        _user, member = _create_member_user(db)
        client.cookies.update(_auth_cookie(admin))

        resp = client.get(f"/api/v1/members/{member.id}/card")
        assert resp.status_code == 200
        data = resp.json()
        assert data["member_id"] == member.id
        assert data["full_name"] == "Mika Roig"
        assert data["member_number"] == "SCB-0001"
        assert verify_card_token(data["token"]) == member.id

    def test_admin_gets_member_card_pdf(self, client, db):
        _ensure_org(db)
        admin = _create_admin(db)
        _user, member = _create_member_user(db)
        client.cookies.update(_auth_cookie(admin))

        resp = client.get(f"/api/v1/members/{member.id}/card/pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:5] == b"%PDF-"

    def test_admin_card_works_for_member_without_user_account(self, client, db):
        # Members without a login (e.g. minors) still get a printable card.
        _ensure_org(db)
        admin = _create_admin(db)
        _user, member = _create_member_user(db)
        member.user_id = None
        db.flush()
        client.cookies.update(_auth_cookie(admin))

        resp = client.get(f"/api/v1/members/{member.id}/card")
        assert resp.status_code == 200
        assert resp.json()["member_id"] == member.id

    def test_member_cannot_view_admin_card_endpoint(self, client, db):
        _ensure_org(db)
        user, member = _create_member_user(db)
        client.cookies.update(_auth_cookie(user))

        resp = client.get(f"/api/v1/members/{member.id}/card")
        assert resp.status_code == 403

    def test_admin_card_unknown_member_404(self, client, db):
        _ensure_org(db)
        admin = _create_admin(db)
        client.cookies.update(_auth_cookie(admin))

        resp = client.get("/api/v1/members/999999/card")
        assert resp.status_code == 404

    def test_admin_card_404_when_module_off(self, client, db):
        _ensure_org(db, member_card=False)
        admin = _create_admin(db)
        _user, member = _create_member_user(db)
        client.cookies.update(_auth_cookie(admin))

        assert client.get(f"/api/v1/members/{member.id}/card").status_code == 404
        assert client.get(f"/api/v1/members/{member.id}/card/pdf").status_code == 404


# --- Member numbering ---


class TestMemberNumbering:
    def test_auto_number_on_create_uses_config(self, client, db):
        _ensure_org(db, prefix="SCB-", padding=4, next_num=1)
        admin = _create_admin(db)
        client.cookies.update(_auth_cookie(admin))

        resp = client.post(
            "/api/v1/members/",
            json={"first_name": "New", "last_name": "One"},
        )
        assert resp.status_code == 201
        assert resp.json()["member_number"] == "SCB-0001"

    def test_allocation_advances_and_is_unique(self, client, db):
        _ensure_org(db, prefix="SCB-", padding=4, next_num=1)
        admin = _create_admin(db)
        client.cookies.update(_auth_cookie(admin))

        numbers = []
        for i in range(3):
            resp = client.post(
                "/api/v1/members/",
                json={"first_name": f"P{i}", "last_name": "X"},
            )
            assert resp.status_code == 201
            numbers.append(resp.json()["member_number"])

        assert numbers == ["SCB-0001", "SCB-0002", "SCB-0003"]
        assert len(set(numbers)) == 3

    def test_allocation_skips_existing_collision(self, client, db):
        _ensure_org(db, prefix="SCB-", padding=4, next_num=1)
        # Pre-seed a member already holding SCB-0001.
        _create_member_user(db, email="held@test.com", number="SCB-0001")
        admin = _create_admin(db)
        client.cookies.update(_auth_cookie(admin))

        resp = client.post(
            "/api/v1/members/",
            json={"first_name": "Next", "last_name": "Free"},
        )
        assert resp.status_code == 201
        assert resp.json()["member_number"] == "SCB-0002"

    def test_assign_numbers_fills_nulls_in_id_order(self, client, db):
        _ensure_org(db, prefix="SCB-", padding=4, next_num=1)
        admin = _create_admin(db)

        # Two members with NULL member_number, created in a known id order.
        m1 = _create_member_user(db, email="m1@test.com", number=None)[1]
        m2 = _create_member_user(db, email="m2@test.com", number=None)[1]
        client.cookies.update(_auth_cookie(admin))

        resp = client.post("/api/v1/members/assign-numbers")
        assert resp.status_code == 200
        assert resp.json()["assigned"] == 2

        db.refresh(m1)
        db.refresh(m2)
        assert m1.member_number == "SCB-0001"
        assert m2.member_number == "SCB-0002"

    def test_assign_numbers_requires_admin(self, client, db):
        _ensure_org(db)
        user, _ = _create_member_user(db)
        client.cookies.update(_auth_cookie(user))

        resp = client.post("/api/v1/members/assign-numbers")
        assert resp.status_code == 403
