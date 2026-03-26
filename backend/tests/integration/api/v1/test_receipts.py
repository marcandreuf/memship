"""Integration tests for receipt and concept endpoints."""

from datetime import date, timedelta
from decimal import Decimal

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.billing.models import Concept, Receipt
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


def _create_user(db, role="admin", suffix="receipt"):
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
            id=1,
            name="Test Organization",
            locale="es",
            timezone="Europe/Madrid",
            currency="EUR",
            date_format="DD/MM/YYYY",
            invoice_prefix="FAC",
            invoice_next_number=1,
            invoice_annual_reset=True,
            default_vat_rate=21.00,
        )
        db.add(org)
        db.flush()
    return db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()


def _create_member(db, suffix="rcpt"):
    person = Person(first_name="María", last_name="García", email=f"maria-{suffix}@test.com")
    db.add(person)
    db.flush()
    mtype = MembershipType(
        name="Full Member",
        slug=f"full-{suffix}",
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
    return member, mtype


def _create_concept(db, suffix="test"):
    concept = Concept(
        name=f"Test Concept {suffix}",
        code=f"test-{suffix}",
        concept_type="manual",
        default_amount=100.00,
        vat_rate=21.00,
    )
    db.add(concept)
    db.flush()
    return concept


# --- Concept Tests ---


class TestConceptCRUD:
    def test_list_concepts_empty(self, client, db):
        user = _create_user(db, "admin", "concept-list")
        resp = client.get("/api/v1/concepts/", cookies=_auth_cookie(user))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_concept(self, client, db):
        user = _create_user(db, "admin", "concept-create")
        resp = client.post(
            "/api/v1/concepts/",
            json={
                "name": "Membership Fee",
                "code": "membership-annual",
                "concept_type": "membership",
                "default_amount": 600,
                "vat_rate": 21,
            },
            cookies=_auth_cookie(user),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Membership Fee"
        assert data["code"] == "membership-annual"
        assert float(data["default_amount"]) == 600.0
        assert float(data["vat_rate"]) == 21.0

    def test_create_concept_duplicate_code(self, client, db):
        user = _create_user(db, "admin", "concept-dup")
        _create_concept(db, "dup")
        resp = client.post(
            "/api/v1/concepts/",
            json={"name": "Another", "code": "test-dup", "concept_type": "manual"},
            cookies=_auth_cookie(user),
        )
        assert resp.status_code == 409

    def test_concepts_require_admin(self, client, db):
        user = _create_user(db, "member", "concept-auth")
        resp = client.get("/api/v1/concepts/", cookies=_auth_cookie(user))
        assert resp.status_code == 403


# --- Receipt CRUD Tests ---


class TestReceiptCRUD:
    def test_create_manual_receipt(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "admin", "rcpt-create")
        member, _ = _create_member(db, "create")

        resp = client.post(
            "/api/v1/receipts/",
            json={
                "member_id": member.id,
                "origin": "manual",
                "description": "Room rental — March 2026",
                "base_amount": 100,
                "vat_rate": 21,
                "emission_date": "2026-03-26",
                "due_date": "2026-04-26",
            },
            cookies=_auth_cookie(user),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["receipt_number"].startswith("FAC-2026-")
        assert float(data["base_amount"]) == 100.0
        assert float(data["vat_amount"]) == 21.0
        assert float(data["total_amount"]) == 121.0

    def test_create_receipt_with_discount(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "admin", "rcpt-disc")
        member, _ = _create_member(db, "disc")

        resp = client.post(
            "/api/v1/receipts/",
            json={
                "member_id": member.id,
                "origin": "manual",
                "description": "Discounted item",
                "base_amount": 200,
                "vat_rate": 21,
                "discount_amount": 10,
                "discount_type": "percentage",
                "emission_date": "2026-03-26",
            },
            cookies=_auth_cookie(user),
        )
        assert resp.status_code == 201
        data = resp.json()
        # 10% of 200 = 20 discount, base = 180, VAT = 37.80, total = 217.80
        assert float(data["base_amount"]) == 180.0
        assert float(data["vat_amount"]) == 37.80
        assert float(data["total_amount"]) == 217.80

    def test_list_receipts(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "admin", "rcpt-list")
        member, _ = _create_member(db, "list")

        # Create a receipt
        client.post(
            "/api/v1/receipts/",
            json={
                "member_id": member.id,
                "origin": "manual",
                "description": "Test",
                "base_amount": 50,
                "vat_rate": 21,
                "emission_date": "2026-03-26",
            },
            cookies=_auth_cookie(user),
        )

        resp = client.get("/api/v1/receipts/", cookies=_auth_cookie(user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["meta"]["total"] >= 1
        assert len(data["items"]) >= 1
        # Check detail fields present
        assert "member_name" in data["items"][0]
        assert "receipt_number" in data["items"][0]

    def test_receipts_require_admin(self, client, db):
        user = _create_user(db, "member", "rcpt-auth")
        resp = client.get("/api/v1/receipts/", cookies=_auth_cookie(user))
        assert resp.status_code == 403


# --- Status Transition Tests ---


class TestReceiptStatusTransitions:
    def _create_receipt(self, client, db, suffix):
        _ensure_org_settings(db)
        user = _create_user(db, "admin", f"rcpt-st-{suffix}")
        member, _ = _create_member(db, f"st-{suffix}")
        resp = client.post(
            "/api/v1/receipts/",
            json={
                "member_id": member.id,
                "origin": "manual",
                "description": "Status test",
                "base_amount": 100,
                "vat_rate": 21,
                "emission_date": "2026-03-26",
            },
            cookies=_auth_cookie(user),
        )
        return resp.json(), user

    def test_emit_receipt(self, client, db):
        receipt, user = self._create_receipt(client, db, "emit")
        resp = client.post(
            f"/api/v1/receipts/{receipt['id']}/emit",
            cookies=_auth_cookie(user),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "emitted"

    def test_pay_receipt(self, client, db):
        receipt, user = self._create_receipt(client, db, "pay")
        # Emit first
        client.post(f"/api/v1/receipts/{receipt['id']}/emit", cookies=_auth_cookie(user))
        # Then pay
        resp = client.post(
            f"/api/v1/receipts/{receipt['id']}/pay",
            json={"payment_method": "cash", "payment_date": "2026-03-26"},
            cookies=_auth_cookie(user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "paid"
        assert data["payment_method"] == "cash"
        assert data["payment_date"] == "2026-03-26"

    def test_return_receipt(self, client, db):
        receipt, user = self._create_receipt(client, db, "ret")
        client.post(f"/api/v1/receipts/{receipt['id']}/emit", cookies=_auth_cookie(user))
        resp = client.post(
            f"/api/v1/receipts/{receipt['id']}/return",
            json={"return_reason": "Insufficient funds"},
            cookies=_auth_cookie(user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "returned"
        assert data["return_reason"] == "Insufficient funds"

    def test_cancel_receipt(self, client, db):
        receipt, user = self._create_receipt(client, db, "cancel")
        resp = client.post(
            f"/api/v1/receipts/{receipt['id']}/cancel",
            cookies=_auth_cookie(user),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_reemit_returned_receipt(self, client, db):
        receipt, user = self._create_receipt(client, db, "reemit")
        client.post(f"/api/v1/receipts/{receipt['id']}/emit", cookies=_auth_cookie(user))
        client.post(
            f"/api/v1/receipts/{receipt['id']}/return",
            json={"return_reason": "Account closed"},
            cookies=_auth_cookie(user),
        )
        resp = client.post(
            f"/api/v1/receipts/{receipt['id']}/reemit",
            cookies=_auth_cookie(user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert data["return_reason"] is None

    def test_cannot_pay_new_receipt(self, client, db):
        """Cannot pay a receipt that hasn't been emitted."""
        receipt, user = self._create_receipt(client, db, "nopay")
        resp = client.post(
            f"/api/v1/receipts/{receipt['id']}/pay",
            json={"payment_method": "cash"},
            cookies=_auth_cookie(user),
        )
        assert resp.status_code == 400

    def test_cannot_cancel_paid_receipt(self, client, db):
        """Cannot cancel a receipt that's already paid."""
        receipt, user = self._create_receipt(client, db, "nocancel")
        client.post(f"/api/v1/receipts/{receipt['id']}/emit", cookies=_auth_cookie(user))
        client.post(
            f"/api/v1/receipts/{receipt['id']}/pay",
            json={"payment_method": "bank_transfer"},
            cookies=_auth_cookie(user),
        )
        resp = client.post(
            f"/api/v1/receipts/{receipt['id']}/cancel",
            cookies=_auth_cookie(user),
        )
        assert resp.status_code == 400


# --- Bulk Generation Tests ---


class TestGenerateMembershipFees:
    def test_generate_fees(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "admin", "bulk-gen")
        member, mtype = _create_member(db, "bulk")

        resp = client.post(
            "/api/v1/receipts/generate-membership-fees",
            json={
                "billing_period_start": "2026-01-01",
                "billing_period_end": "2026-12-31",
                "emission_date": "2026-03-26",
                "due_date": "2026-04-26",
            },
            cookies=_auth_cookie(user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["generated"] >= 1

    def test_no_duplicate_fees(self, client, db):
        """Running generation twice for same period should not create duplicates."""
        _ensure_org_settings(db)
        user = _create_user(db, "admin", "bulk-nodup")
        member, _ = _create_member(db, "nodup")

        payload = {
            "billing_period_start": "2026-01-01",
            "billing_period_end": "2026-12-31",
            "emission_date": "2026-03-26",
        }
        resp1 = client.post(
            "/api/v1/receipts/generate-membership-fees",
            json=payload,
            cookies=_auth_cookie(user),
        )
        count1 = resp1.json()["generated"]

        resp2 = client.post(
            "/api/v1/receipts/generate-membership-fees",
            json=payload,
            cookies=_auth_cookie(user),
        )
        count2 = resp2.json()["generated"]
        assert count2 == 0  # No duplicates


# --- VAT Calculation Tests ---


class TestReceiptPDF:
    def test_download_pdf(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "admin", "pdf-dl")
        member, _ = _create_member(db, "pdf")

        # Create and emit a receipt
        create_resp = client.post(
            "/api/v1/receipts/",
            json={
                "member_id": member.id,
                "origin": "manual",
                "description": "PDF test receipt",
                "base_amount": 100,
                "vat_rate": 21,
                "emission_date": "2026-03-26",
            },
            cookies=_auth_cookie(user),
        )
        receipt_id = create_resp.json()["id"]
        client.post(f"/api/v1/receipts/{receipt_id}/emit", cookies=_auth_cookie(user))

        resp = client.get(f"/api/v1/receipts/{receipt_id}/pdf", cookies=_auth_cookie(user))
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:5] == b"%PDF-"  # Valid PDF header

    def test_member_cannot_download_other_receipt(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, "admin", "pdf-other-admin")
        member_user = _create_user(db, "member", "pdf-other-member")
        member, _ = _create_member(db, "pdf-other")

        create_resp = client.post(
            "/api/v1/receipts/",
            json={
                "member_id": member.id,
                "origin": "manual",
                "description": "Other member receipt",
                "base_amount": 50,
                "vat_rate": 21,
                "emission_date": "2026-03-26",
            },
            cookies=_auth_cookie(admin),
        )
        receipt_id = create_resp.json()["id"]

        # Member trying to access another member's receipt
        resp = client.get(f"/api/v1/receipts/{receipt_id}/pdf", cookies=_auth_cookie(member_user))
        assert resp.status_code == 403


class TestVATCalculation:
    def test_standard_vat(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "admin", "vat-std")
        member, _ = _create_member(db, "vat-std")

        resp = client.post(
            "/api/v1/receipts/",
            json={
                "member_id": member.id,
                "origin": "manual",
                "description": "VAT test",
                "base_amount": 100,
                "vat_rate": 21,
                "emission_date": "2026-03-26",
            },
            cookies=_auth_cookie(user),
        )
        data = resp.json()
        assert float(data["vat_amount"]) == 21.0
        assert float(data["total_amount"]) == 121.0

    def test_reduced_vat(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "admin", "vat-red")
        member, _ = _create_member(db, "vat-red")

        resp = client.post(
            "/api/v1/receipts/",
            json={
                "member_id": member.id,
                "origin": "manual",
                "description": "Reduced VAT test",
                "base_amount": 50.50,
                "vat_rate": 10,
                "emission_date": "2026-03-26",
            },
            cookies=_auth_cookie(user),
        )
        data = resp.json()
        assert float(data["vat_amount"]) == 5.05
        assert float(data["total_amount"]) == 55.55

    def test_zero_vat(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "admin", "vat-zero")
        member, _ = _create_member(db, "vat-zero")

        resp = client.post(
            "/api/v1/receipts/",
            json={
                "member_id": member.id,
                "origin": "manual",
                "description": "Exempt",
                "base_amount": 75,
                "vat_rate": 0,
                "emission_date": "2026-03-26",
            },
            cookies=_auth_cookie(user),
        )
        data = resp.json()
        assert float(data["vat_amount"]) == 0
        assert float(data["total_amount"]) == 75.0
