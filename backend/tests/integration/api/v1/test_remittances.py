"""Integration tests for remittance (SEPA batch) endpoints."""

import json
from datetime import date, timedelta
from decimal import Decimal

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.billing.models import Concept, Receipt, SepaMandate
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


def _create_user(db, role="admin", suffix="rem"):
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


def _ensure_org_settings(db):
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
            creditor_id="ES12000B12345678",
            bank_iban="ES9121000418450200051332",
            bank_bic="CAIXESBBXXX",
        )
        db.add(org)
        db.flush()
    else:
        if not existing.creditor_id:
            existing.creditor_id = "ES12000B12345678"
            existing.bank_iban = "ES9121000418450200051332"
            existing.bank_bic = "CAIXESBBXXX"
            db.flush()
    return db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()


def _create_member_with_mandate(db, suffix="rem"):
    """Create a member with an active SEPA mandate and return (member, mandate)."""
    person = Person(first_name="Test", last_name=f"Member-{suffix}", email=f"test-{suffix}@test.com")
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

    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    mandate = SepaMandate(
        member_id=member.id,
        mandate_reference=f"FAC-M{suffix}-001",
        creditor_id=org.creditor_id,
        debtor_name=f"Test Member-{suffix}",
        debtor_iban="ES7921000813610123456789",
        debtor_bic="BBVAESMMXXX",
        mandate_type="recurrent",
        signature_method="paper",
        status="active",
        signed_at=date(2026, 4, 1),
    )
    db.add(mandate)
    db.flush()
    return member, mandate


def _create_receipt(db, member_id, user_id, suffix="rem", status="emitted"):
    """Create a receipt for a member."""
    concept = Concept(
        name=f"Fee-{suffix}",
        code=f"fee-{suffix}",
        concept_type="membership",
        default_amount=50.00,
        vat_rate=21.00,
    )
    db.add(concept)
    db.flush()

    receipt = Receipt(
        receipt_number=f"FAC-2026-{suffix}",
        member_id=member_id,
        concept_id=concept.id,
        origin="membership",
        description=f"Monthly fee {suffix}",
        base_amount=Decimal("50.00"),
        vat_rate=Decimal("21.00"),
        vat_amount=Decimal("10.50"),
        total_amount=Decimal("60.50"),
        status=status,
        emission_date=date.today(),
        is_batchable=True,
        created_by=user_id,
    )
    db.add(receipt)
    db.flush()
    return receipt


class TestRemittanceCRUD:
    def test_create_remittance(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-c1")
        m1, _ = _create_member_with_mandate(db, suffix="rem-c1")
        r1 = _create_receipt(db, m1.id, admin.id, suffix="rem-c1-01")

        resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [r1.id], "due_date": "2026-05-01"},
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "draft"
        assert data["receipt_count"] == 1
        assert data["remittance_number"].startswith("REM-")
        assert float(data["total_amount"]) == 60.50

    def test_create_rejects_non_emitted_receipts(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-c2")
        m1, _ = _create_member_with_mandate(db, suffix="rem-c2")
        r1 = _create_receipt(db, m1.id, admin.id, suffix="rem-c2-01", status="pending")

        resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [r1.id], "due_date": "2026-05-01"},
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 400

    def test_create_rejects_receipts_without_mandate(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-c3")
        # Create member WITHOUT mandate
        person = Person(first_name="No", last_name="Mandate", email="no-mandate-rem@test.com")
        db.add(person)
        db.flush()
        mtype = MembershipType(name="NoMandate-rem", slug="nomandate-rem", base_price=50.00, billing_frequency="monthly")
        db.add(mtype)
        db.flush()
        member = Member(person_id=person.id, membership_type_id=mtype.id, member_number="M-noman", status="active")
        db.add(member)
        db.flush()

        r1 = _create_receipt(db, member.id, admin.id, suffix="rem-c3-01")

        resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [r1.id], "due_date": "2026-05-01"},
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 400
        assert "mandate" in str(resp.json()["detail"]).lower()

    def test_create_rejects_already_batched_receipt(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-c4")
        m1, _ = _create_member_with_mandate(db, suffix="rem-c4")
        r1 = _create_receipt(db, m1.id, admin.id, suffix="rem-c4-01")

        # Create first remittance
        client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [r1.id], "due_date": "2026-05-01"},
            cookies=_auth_cookie(admin),
        )

        # Try to batch same receipt again
        resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [r1.id], "due_date": "2026-05-01"},
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 400

    def test_list_remittances(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-l1")
        m1, _ = _create_member_with_mandate(db, suffix="rem-l1")
        r1 = _create_receipt(db, m1.id, admin.id, suffix="rem-l1-01")

        client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [r1.id], "due_date": "2026-05-01"},
            cookies=_auth_cookie(admin),
        )

        resp = client.get("/api/v1/remittances/", cookies=_auth_cookie(admin))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_get_remittance_detail(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-g1")
        m1, _ = _create_member_with_mandate(db, suffix="rem-g1")
        r1 = _create_receipt(db, m1.id, admin.id, suffix="rem-g1-01")

        create_resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [r1.id], "due_date": "2026-05-01"},
            cookies=_auth_cookie(admin),
        )
        rem_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/remittances/{rem_id}", cookies=_auth_cookie(admin))
        assert resp.status_code == 200
        assert len(resp.json()["receipts"]) == 1


class TestSepaXmlWorkflow:
    def test_generate_xml(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-xml1")
        m1, _ = _create_member_with_mandate(db, suffix="rem-xml1")
        r1 = _create_receipt(db, m1.id, admin.id, suffix="rem-xml1-01")

        create_resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [r1.id], "due_date": "2026-05-01"},
            cookies=_auth_cookie(admin),
        )
        rem_id = create_resp.json()["id"]

        resp = client.post(f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin))
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"
        assert resp.json()["sepa_file_path"] is not None

    def test_download_xml(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-xml2")
        m1, _ = _create_member_with_mandate(db, suffix="rem-xml2")
        r1 = _create_receipt(db, m1.id, admin.id, suffix="rem-xml2-01")

        create_resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [r1.id], "due_date": "2026-05-01"},
            cookies=_auth_cookie(admin),
        )
        rem_id = create_resp.json()["id"]

        client.post(f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin))

        resp = client.get(f"/api/v1/remittances/{rem_id}/download-xml", cookies=_auth_cookie(admin))
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/xml"
        assert b"pain.008.001.02" in resp.content

    def test_mark_submitted(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-sub1")
        m1, _ = _create_member_with_mandate(db, suffix="rem-sub1")
        r1 = _create_receipt(db, m1.id, admin.id, suffix="rem-sub1-01")

        create_resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [r1.id], "due_date": "2026-05-01"},
            cookies=_auth_cookie(admin),
        )
        rem_id = create_resp.json()["id"]
        client.post(f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin))

        resp = client.post(f"/api/v1/remittances/{rem_id}/mark-submitted", cookies=_auth_cookie(admin))
        assert resp.status_code == 200
        assert resp.json()["status"] == "submitted"

    def test_cannot_submit_draft(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-sub2")
        m1, _ = _create_member_with_mandate(db, suffix="rem-sub2")
        r1 = _create_receipt(db, m1.id, admin.id, suffix="rem-sub2-01")

        create_resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [r1.id], "due_date": "2026-05-01"},
            cookies=_auth_cookie(admin),
        )
        rem_id = create_resp.json()["id"]

        resp = client.post(f"/api/v1/remittances/{rem_id}/mark-submitted", cookies=_auth_cookie(admin))
        assert resp.status_code == 400


class TestImportReturns:
    def test_import_returns(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-ret1")
        m1, _ = _create_member_with_mandate(db, suffix="rem-ret1")
        r1 = _create_receipt(db, m1.id, admin.id, suffix="rem-ret1-01")
        receipt_number = r1.receipt_number

        create_resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [r1.id], "due_date": "2026-05-01"},
            cookies=_auth_cookie(admin),
        )
        rem_id = create_resp.json()["id"]
        client.post(f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin))
        client.post(f"/api/v1/remittances/{rem_id}/mark-submitted", cookies=_auth_cookie(admin))

        return_data = json.dumps([
            {"receipt_number": receipt_number, "reason": "Insufficient funds"},
        ]).encode()

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/import-returns",
            files={"file": ("returns.json", return_data, "application/json")},
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["processed"] == 1
        assert result["returned"] == 1
        assert result["not_found"] == 0

    def test_import_returns_not_found(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-ret2")
        m1, _ = _create_member_with_mandate(db, suffix="rem-ret2")
        r1 = _create_receipt(db, m1.id, admin.id, suffix="rem-ret2-01")

        create_resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [r1.id], "due_date": "2026-05-01"},
            cookies=_auth_cookie(admin),
        )
        rem_id = create_resp.json()["id"]
        client.post(f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin))
        client.post(f"/api/v1/remittances/{rem_id}/mark-submitted", cookies=_auth_cookie(admin))

        return_data = json.dumps([
            {"receipt_number": "FAKE-0000", "reason": "Unknown"},
        ]).encode()

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/import-returns",
            files={"file": ("returns.json", return_data, "application/json")},
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["not_found"] == 1


class TestRemittanceLifecycle:
    def test_full_lifecycle(self, client, db):
        """Draft -> Ready -> Submitted -> Processed -> Closed."""
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-lc1")
        m1, _ = _create_member_with_mandate(db, suffix="rem-lc1")
        r1 = _create_receipt(db, m1.id, admin.id, suffix="rem-lc1-01")

        # Create (draft)
        create_resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [r1.id], "due_date": "2026-05-01"},
            cookies=_auth_cookie(admin),
        )
        rem_id = create_resp.json()["id"]
        assert create_resp.json()["status"] == "draft"

        # Generate XML (-> ready)
        resp = client.post(f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin))
        assert resp.json()["status"] == "ready"

        # Submit (-> submitted)
        resp = client.post(f"/api/v1/remittances/{rem_id}/mark-submitted", cookies=_auth_cookie(admin))
        assert resp.json()["status"] == "submitted"

        # Import returns (-> processed)
        return_data = json.dumps([]).encode()
        resp = client.post(
            f"/api/v1/remittances/{rem_id}/import-returns",
            files={"file": ("returns.json", return_data, "application/json")},
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 200

        # Close (-> closed)
        resp = client.post(f"/api/v1/remittances/{rem_id}/close", cookies=_auth_cookie(admin))
        assert resp.json()["status"] == "closed"

    def test_cancel_draft(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-cn1")
        m1, _ = _create_member_with_mandate(db, suffix="rem-cn1")
        r1 = _create_receipt(db, m1.id, admin.id, suffix="rem-cn1-01")

        create_resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [r1.id], "due_date": "2026-05-01"},
            cookies=_auth_cookie(admin),
        )
        rem_id = create_resp.json()["id"]

        resp = client.post(f"/api/v1/remittances/{rem_id}/cancel", cookies=_auth_cookie(admin))
        assert resp.json()["status"] == "cancelled"

    def test_cancel_unlinks_receipts(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-cn2")
        m1, _ = _create_member_with_mandate(db, suffix="rem-cn2")
        r1 = _create_receipt(db, m1.id, admin.id, suffix="rem-cn2-01")
        receipt_id = r1.id

        create_resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [r1.id], "due_date": "2026-05-01"},
            cookies=_auth_cookie(admin),
        )
        rem_id = create_resp.json()["id"]

        client.post(f"/api/v1/remittances/{rem_id}/cancel", cookies=_auth_cookie(admin))

        # Verify receipt is unlinked
        receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
        assert receipt.remittance_id is None

    def test_stats_endpoint(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-st1")
        m1, _ = _create_member_with_mandate(db, suffix="rem-st1")
        r1 = _create_receipt(db, m1.id, admin.id, suffix="rem-st1-01")

        create_resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [r1.id], "due_date": "2026-05-01"},
            cookies=_auth_cookie(admin),
        )
        rem_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/remittances/{rem_id}/stats", cookies=_auth_cookie(admin))
        assert resp.status_code == 200
        assert resp.json()["total_receipts"] == 1


class TestRemittanceAuth:
    def test_member_cannot_create_remittance(self, client, db):
        member_user = _create_user(db, role="member", suffix="rem-auth1")
        resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [1], "due_date": "2026-05-01"},
            cookies=_auth_cookie(member_user),
        )
        assert resp.status_code == 403

    def test_member_cannot_list_remittances(self, client, db):
        member_user = _create_user(db, role="member", suffix="rem-auth2")
        resp = client.get("/api/v1/remittances/", cookies=_auth_cookie(member_user))
        assert resp.status_code == 403
