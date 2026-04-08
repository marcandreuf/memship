"""Integration tests for SEPA mandate endpoints."""

from datetime import date

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.billing.models import SepaMandate
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


def _create_user(db, role="admin", suffix="mnd"):
    person = Person(first_name="Admin", last_name="User", email=f"{suffix}-{role}@test.com")
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


def _ensure_org_settings(db, creditor_id="ES12000B12345678"):
    existing = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not existing:
        org = OrganizationSettings(
            id=1,
            name="Club Test",
            locale="es",
            timezone="Europe/Madrid",
            currency="EUR",
            date_format="DD/MM/YYYY",
            invoice_prefix="FAC",
            invoice_next_number=1,
            invoice_annual_reset=True,
            default_vat_rate=21.00,
            creditor_id=creditor_id,
            bank_iban="ES9121000418450200051332",
            bank_bic="CAIXESBBXXX",
        )
        db.add(org)
        db.flush()
    else:
        if creditor_id and not existing.creditor_id:
            existing.creditor_id = creditor_id
            existing.bank_iban = "ES9121000418450200051332"
            existing.bank_bic = "CAIXESBBXXX"
            db.flush()
    return db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()


def _create_member(db, suffix="mnd"):
    person = Person(first_name="Juan", last_name="Pérez", email=f"juan-{suffix}@test.com")
    db.add(person)
    db.flush()
    mtype = MembershipType(
        name=f"Standard-{suffix}",
        slug=f"standard-{suffix}",
        base_price=50.00,
        billing_frequency="monthly",
    )
    db.add(mtype)
    db.flush()
    member = Member(
        person_id=person.id,
        membership_type_id=mtype.id,
        member_number=f"M-{suffix}",
        status="active",
    )
    db.add(member)
    db.flush()
    return member, person


def _mandate_payload(member_id, **overrides):
    base = {
        "member_id": member_id,
        "debtor_name": "Juan Pérez",
        "debtor_iban": "ES7921000813610123456789",
        "signed_at": "2026-04-01",
    }
    base.update(overrides)
    return base


class TestMandateCRUD:
    def test_create_mandate(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="mnd-c1")
        member, _ = _create_member(db, suffix="mnd-c1")

        resp = client.post(
            "/api/v1/mandates/",
            json=_mandate_payload(member.id),
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "active"
        assert data["debtor_name"] == "Juan Pérez"
        assert data["debtor_iban"] == "ES7921000813610123456789"
        assert data["mandate_reference"].startswith("FAC-")
        assert data["creditor_id"] == "ES12000B12345678"

    def test_create_mandate_requires_creditor_id(self, client, db):
        _ensure_org_settings(db, creditor_id=None)
        # Clear creditor_id
        org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
        org.creditor_id = None
        db.flush()

        admin = _create_user(db, suffix="mnd-c2")
        member, _ = _create_member(db, suffix="mnd-c2")

        resp = client.post(
            "/api/v1/mandates/",
            json=_mandate_payload(member.id),
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 400
        assert "creditor" in resp.json()["detail"].lower()

    def test_create_mandate_invalid_iban(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="mnd-c3")
        member, _ = _create_member(db, suffix="mnd-c3")

        resp = client.post(
            "/api/v1/mandates/",
            json=_mandate_payload(member.id, debtor_iban="INVALID"),
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 422

    def test_list_mandates(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="mnd-l1")
        member, _ = _create_member(db, suffix="mnd-l1")

        # Create a mandate
        client.post(
            "/api/v1/mandates/",
            json=_mandate_payload(member.id),
            cookies=_auth_cookie(admin),
        )

        resp = client.get("/api/v1/mandates/", cookies=_auth_cookie(admin))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_list_mandates_filter_by_member(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="mnd-l2")
        m1, _ = _create_member(db, suffix="mnd-l2a")
        m2, _ = _create_member(db, suffix="mnd-l2b")

        client.post("/api/v1/mandates/", json=_mandate_payload(m1.id), cookies=_auth_cookie(admin))
        client.post("/api/v1/mandates/", json=_mandate_payload(m2.id, debtor_name="Other"), cookies=_auth_cookie(admin))

        resp = client.get(f"/api/v1/mandates/?member_id={m1.id}", cookies=_auth_cookie(admin))
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["member_id"] == m1.id

    def test_list_mandates_search(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="mnd-ls")
        member, _ = _create_member(db, suffix="mnd-ls")

        client.post(
            "/api/v1/mandates/",
            json=_mandate_payload(member.id, debtor_name="Unique SearchName"),
            cookies=_auth_cookie(admin),
        )

        resp = client.get("/api/v1/mandates/?search=SearchName", cookies=_auth_cookie(admin))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_get_mandate(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="mnd-g1")
        member, _ = _create_member(db, suffix="mnd-g1")

        create_resp = client.post(
            "/api/v1/mandates/",
            json=_mandate_payload(member.id),
            cookies=_auth_cookie(admin),
        )
        mandate_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/mandates/{mandate_id}", cookies=_auth_cookie(admin))
        assert resp.status_code == 200
        assert resp.json()["id"] == mandate_id

    def test_update_mandate(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="mnd-u1")
        member, _ = _create_member(db, suffix="mnd-u1")

        create_resp = client.post(
            "/api/v1/mandates/",
            json=_mandate_payload(member.id),
            cookies=_auth_cookie(admin),
        )
        mandate_id = create_resp.json()["id"]

        resp = client.put(
            f"/api/v1/mandates/{mandate_id}",
            json={"debtor_name": "Juan Updated"},
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["debtor_name"] == "Juan Updated"

    def test_cancel_mandate(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="mnd-cn1")
        member, _ = _create_member(db, suffix="mnd-cn1")

        create_resp = client.post(
            "/api/v1/mandates/",
            json=_mandate_payload(member.id),
            cookies=_auth_cookie(admin),
        )
        mandate_id = create_resp.json()["id"]

        resp = client.post(f"/api/v1/mandates/{mandate_id}/cancel", cookies=_auth_cookie(admin))
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"
        assert resp.json()["cancelled_at"] is not None

    def test_cancel_already_cancelled_fails(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="mnd-cn2")
        member, _ = _create_member(db, suffix="mnd-cn2")

        create_resp = client.post(
            "/api/v1/mandates/",
            json=_mandate_payload(member.id),
            cookies=_auth_cookie(admin),
        )
        mandate_id = create_resp.json()["id"]

        client.post(f"/api/v1/mandates/{mandate_id}/cancel", cookies=_auth_cookie(admin))
        resp = client.post(f"/api/v1/mandates/{mandate_id}/cancel", cookies=_auth_cookie(admin))
        assert resp.status_code == 400

    def test_update_cancelled_mandate_fails(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="mnd-uc1")
        member, _ = _create_member(db, suffix="mnd-uc1")

        create_resp = client.post(
            "/api/v1/mandates/",
            json=_mandate_payload(member.id),
            cookies=_auth_cookie(admin),
        )
        mandate_id = create_resp.json()["id"]
        client.post(f"/api/v1/mandates/{mandate_id}/cancel", cookies=_auth_cookie(admin))

        resp = client.put(
            f"/api/v1/mandates/{mandate_id}",
            json={"debtor_name": "Should Fail"},
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 400


class TestMandateAuth:
    def test_member_cannot_create_mandate(self, client, db):
        _ensure_org_settings(db)
        member_user = _create_user(db, role="member", suffix="mnd-auth1")
        member, _ = _create_member(db, suffix="mnd-auth1")

        resp = client.post(
            "/api/v1/mandates/",
            json=_mandate_payload(member.id),
            cookies=_auth_cookie(member_user),
        )
        assert resp.status_code == 403

    def test_member_cannot_list_mandates(self, client, db):
        member_user = _create_user(db, role="member", suffix="mnd-auth2")
        resp = client.get("/api/v1/mandates/", cookies=_auth_cookie(member_user))
        assert resp.status_code == 403


class TestMemberMandate:
    def test_member_views_own_mandate(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="mnd-mm1a")
        member, person = _create_member(db, suffix="mnd-mm1")

        # Create user account for the member's person
        member_user = User(
            person_id=person.id,
            email=person.email,
            password_hash=hash_password("password123"),
            role="member",
            is_active=True,
        )
        db.add(member_user)
        db.flush()

        # Admin creates mandate
        client.post(
            "/api/v1/mandates/",
            json=_mandate_payload(member.id),
            cookies=_auth_cookie(admin),
        )

        # Member views their mandate
        resp = client.get("/api/v1/members/me/mandate", cookies=_auth_cookie(member_user))
        assert resp.status_code == 200
        assert resp.json()["member_id"] == member.id

    def test_member_no_mandate_returns_204(self, client, db):
        _ensure_org_settings(db)
        member, person = _create_member(db, suffix="mnd-mm2")

        member_user = User(
            person_id=person.id,
            email=person.email,
            password_hash=hash_password("password123"),
            role="member",
            is_active=True,
        )
        db.add(member_user)
        db.flush()

        resp = client.get("/api/v1/members/me/mandate", cookies=_auth_cookie(member_user))
        assert resp.status_code == 204


class TestMandateUpload:
    def test_upload_signed_document(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="mnd-up1")
        member, _ = _create_member(db, suffix="mnd-up1")

        create_resp = client.post(
            "/api/v1/mandates/",
            json=_mandate_payload(member.id),
            cookies=_auth_cookie(admin),
        )
        mandate_id = create_resp.json()["id"]

        resp = client.post(
            f"/api/v1/mandates/{mandate_id}/upload-signed",
            files={"file": ("signed_mandate.pdf", b"%PDF-1.4 fake content", "application/pdf")},
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["document_path"] is not None

    def test_upload_rejects_invalid_extension(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="mnd-up2")
        member, _ = _create_member(db, suffix="mnd-up2")

        create_resp = client.post(
            "/api/v1/mandates/",
            json=_mandate_payload(member.id),
            cookies=_auth_cookie(admin),
        )
        mandate_id = create_resp.json()["id"]

        resp = client.post(
            f"/api/v1/mandates/{mandate_id}/upload-signed",
            files={"file": ("mandate.exe", b"malicious", "application/octet-stream")},
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 422


class TestMandateReference:
    def test_unique_references_per_member(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="mnd-ref")
        member, _ = _create_member(db, suffix="mnd-ref")

        r1 = client.post("/api/v1/mandates/", json=_mandate_payload(member.id), cookies=_auth_cookie(admin))
        # Cancel first mandate so we can create another
        client.post(f"/api/v1/mandates/{r1.json()['id']}/cancel", cookies=_auth_cookie(admin))

        r2 = client.post("/api/v1/mandates/", json=_mandate_payload(member.id), cookies=_auth_cookie(admin))
        assert r1.json()["mandate_reference"] != r2.json()["mandate_reference"]
