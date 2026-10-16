"""Integration tests for remittance (SEPA batch) endpoints."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.billing.models import Concept, Receipt, Remittance, SepaMandate
from app.domains.billing.remittance_service import label_members
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


def _create_user(db, role="admin", suffix="rem"):
    person = Person(first_name="Admin", last_name="User", email=f"{suffix}-{role}@examplee6e3b1.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=f"{suffix}-{role}@examplee6e3b1.com",
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id)}


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
    person = Person(first_name="Test", last_name=f"Member-{suffix}", email=f"test-{suffix}@examplee6e3b1.com")
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
        person = Person(first_name="No", last_name="Mandate", email="no-mandate-rem@examplee6e3b1.com")
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

    def test_list_remittances_honours_per_page(self, client, db):
        # The route took `page_size`, a name nothing sends (#255).
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-pp")
        for i in range(2):
            member, _ = _create_member_with_mandate(db, suffix=f"rem-pp{i}")
            receipt = _create_receipt(db, member.id, admin.id, suffix=f"rem-pp{i}")
            client.post(
                "/api/v1/remittances/",
                json={"receipt_ids": [receipt.id], "due_date": "2026-05-01"},
                cookies=_auth_cookie(admin),
            )

        resp = client.get("/api/v1/remittances/?page=1&per_page=1", cookies=_auth_cookie(admin))
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 1
        assert body["meta"]["per_page"] == 1
        assert body["meta"]["total"] >= 2

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

    def test_xml_orders_transactions_by_receipt_id(self, client, db):
        """The receipts reach the SEPA file in a defined order.

        The query behind it had no `ORDER BY`, so the bank received the batch in
        whatever order PostgreSQL happened to return and two exports of the same
        remittance could differ. See #277 — the same missing clause also made
        the close fan-out non-deterministic.
        """
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-xmlord")
        m1, _ = _create_member_with_mandate(db, suffix="rem-xmlord")
        receipts = [
            _create_receipt(db, m1.id, admin.id, suffix=f"rem-xmlord-{n:02d}")
            for n in range(1, 4)
        ]

        create_resp = client.post(
            "/api/v1/remittances/",
            json={
                "receipt_ids": [r.id for r in receipts],
                "due_date": "2026-05-01",
            },
            cookies=_auth_cookie(admin),
        )
        rem_id = create_resp.json()["id"]

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin)
        )
        assert resp.status_code == 200

        xml = client.get(
            f"/api/v1/remittances/{rem_id}/download-xml", cookies=_auth_cookie(admin)
        ).content.decode()

        # Each transaction's description carries its receipt number, so the
        # position of each number in the document is the transaction order.
        positions = [xml.index(r.receipt_number) for r in receipts]
        assert positions == sorted(positions), (
            f"receipts appear out of id order: {positions}"
        )

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

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/import-returns",
            json=[{"receipt_number": receipt_number, "reason": "Insufficient funds"}],
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

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/import-returns",
            json=[{"receipt_number": "FAKE-0000", "reason": "Unknown"}],
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
        resp = client.post(
            f"/api/v1/remittances/{rem_id}/import-returns",
            json=[],
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


class TestCloseReconcilesPayments:
    """SEPA reports only failures, so closing settles everything still in flight."""

    FANOUT = "app.tasks.billing_tasks.payment_notifications_fanout.delay"

    def _submitted_remittance(self, client, admin, receipt_ids, due_date="2026-05-01"):
        create_resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": receipt_ids, "due_date": due_date},
            cookies=_auth_cookie(admin),
        )
        rem_id = create_resp.json()["id"]
        client.post(f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin))
        client.post(f"/api/v1/remittances/{rem_id}/mark-submitted", cookies=_auth_cookie(admin))
        return rem_id

    def test_a_clean_batch_closes_straight_from_submitted(self, client, db):
        """Nothing to import means nothing ever set 'processed'."""
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-cl1")
        m1, _ = _create_member_with_mandate(db, suffix="rem-cl1")
        r1 = _create_receipt(db, m1.id, admin.id, suffix="rem-cl1-01")
        r2 = _create_receipt(db, m1.id, admin.id, suffix="rem-cl1-02")
        rem_id = self._submitted_remittance(client, admin, [r1.id, r2.id])

        resp = client.post(f"/api/v1/remittances/{rem_id}/close", cookies=_auth_cookie(admin))
        assert resp.status_code == 200
        assert resp.json()["status"] == "closed"

        db.expire_all()
        for receipt_id in (r1.id, r2.id):
            receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
            assert receipt.status == "paid"
            assert receipt.payment_method == "direct_debit"
            assert receipt.payment_date == date(2026, 5, 1)

    def test_returned_receipts_are_left_alone(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-cl2")
        m1, _ = _create_member_with_mandate(db, suffix="rem-cl2")
        settled = _create_receipt(db, m1.id, admin.id, suffix="rem-cl2-01")
        bounced = _create_receipt(db, m1.id, admin.id, suffix="rem-cl2-02")
        bounced_number = bounced.receipt_number
        rem_id = self._submitted_remittance(client, admin, [settled.id, bounced.id])

        client.post(
            f"/api/v1/remittances/{rem_id}/import-returns",
            json=[{"receipt_number": bounced_number, "reason": "Insufficient funds"}],
            cookies=_auth_cookie(admin),
        )
        client.post(f"/api/v1/remittances/{rem_id}/close", cookies=_auth_cookie(admin))

        db.expire_all()
        assert db.query(Receipt).filter(Receipt.id == settled.id).first().status == "paid"
        returned = db.query(Receipt).filter(Receipt.id == bounced.id).first()
        assert returned.status == "returned"
        assert returned.payment_date is None

    def test_cancelled_and_inactive_receipts_are_left_alone(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-cl3")
        m1, _ = _create_member_with_mandate(db, suffix="rem-cl3")
        settled = _create_receipt(db, m1.id, admin.id, suffix="rem-cl3-01")
        gone = _create_receipt(db, m1.id, admin.id, suffix="rem-cl3-02")
        rem_id = self._submitted_remittance(client, admin, [settled.id, gone.id])

        gone.status = "cancelled"
        gone.is_active = False
        db.flush()

        client.post(f"/api/v1/remittances/{rem_id}/close", cookies=_auth_cookie(admin))

        db.expire_all()
        assert db.query(Receipt).filter(Receipt.id == settled.id).first().status == "paid"
        assert db.query(Receipt).filter(Receipt.id == gone.id).first().status == "cancelled"

    def test_an_overdue_receipt_settles_too(self, client, db):
        """A batched receipt past its due date is still collected by the bank."""
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-cl4")
        m1, _ = _create_member_with_mandate(db, suffix="rem-cl4")
        late = _create_receipt(db, m1.id, admin.id, suffix="rem-cl4-01", status="overdue")
        rem_id = self._submitted_remittance(client, admin, [late.id])

        client.post(f"/api/v1/remittances/{rem_id}/close", cookies=_auth_cookie(admin))

        db.expire_all()
        assert db.query(Receipt).filter(Receipt.id == late.id).first().status == "paid"

    def test_a_second_close_changes_nothing(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-cl5")
        m1, _ = _create_member_with_mandate(db, suffix="rem-cl5")
        r1 = _create_receipt(db, m1.id, admin.id, suffix="rem-cl5-01")
        rem_id = self._submitted_remittance(client, admin, [r1.id])

        client.post(f"/api/v1/remittances/{rem_id}/close", cookies=_auth_cookie(admin))
        db.expire_all()
        first_payment_date = (
            db.query(Receipt).filter(Receipt.id == r1.id).first().payment_date
        )

        with patch(self.FANOUT) as delay:
            resp = client.post(
                f"/api/v1/remittances/{rem_id}/close", cookies=_auth_cookie(admin)
            )

        assert resp.status_code == 400
        delay.assert_not_called()
        db.expire_all()
        receipt = db.query(Receipt).filter(Receipt.id == r1.id).first()
        assert receipt.status == "paid"
        assert receipt.payment_date == first_payment_date
        remittance = db.query(Remittance).filter(Remittance.id == rem_id).first()
        assert remittance.status == "closed"

    def test_closing_queues_one_fanout_job_for_the_batch(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-cl6")
        m1, _ = _create_member_with_mandate(db, suffix="rem-cl6")
        r1 = _create_receipt(db, m1.id, admin.id, suffix="rem-cl6-01")
        r2 = _create_receipt(db, m1.id, admin.id, suffix="rem-cl6-02")
        rem_id = self._submitted_remittance(client, admin, [r1.id, r2.id])

        with patch(self.FANOUT) as delay:
            resp = client.post(
                f"/api/v1/remittances/{rem_id}/close", cookies=_auth_cookie(admin)
            )

        assert resp.status_code == 200
        delay.assert_called_once_with([r1.id, r2.id])

    def test_a_batch_with_nothing_left_to_settle_notifies_nothing(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-cl7")
        m1, _ = _create_member_with_mandate(db, suffix="rem-cl7")
        r1 = _create_receipt(db, m1.id, admin.id, suffix="rem-cl7-01")
        receipt_number = r1.receipt_number
        rem_id = self._submitted_remittance(client, admin, [r1.id])

        client.post(
            f"/api/v1/remittances/{rem_id}/import-returns",
            json=[{"receipt_number": receipt_number, "reason": "No account"}],
            cookies=_auth_cookie(admin),
        )

        with patch(self.FANOUT) as delay:
            resp = client.post(
                f"/api/v1/remittances/{rem_id}/close", cookies=_auth_cookie(admin)
            )

        assert resp.status_code == 200
        delay.assert_not_called()


class TestReturnedReceiptCanBeCollectedAgain:
    """A returned direct debit must be re-collectable.

    An insufficient-funds return is routine, not exceptional. `create_remittance`
    refuses a receipt that already holds a `remittance_id`, and the only other
    place that clears one is `cancel_remittance`, which a submitted or closed
    batch cannot reach — so without re-emit releasing the receipt, retrying a
    returned collection needed a hand-written UPDATE.
    """

    def _returned_receipt(self, client, db, suffix):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix=suffix)
        member, _ = _create_member_with_mandate(db, suffix=suffix)
        receipt = _create_receipt(db, member.id, admin.id, suffix=f"{suffix}-01")

        created = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [receipt.id], "due_date": "2026-05-01"},
            cookies=_auth_cookie(admin),
        )
        assert created.status_code == 201
        remittance_id = created.json()["id"]

        client.post(f"/api/v1/remittances/{remittance_id}/generate-xml", cookies=_auth_cookie(admin))
        client.post(f"/api/v1/remittances/{remittance_id}/mark-submitted", cookies=_auth_cookie(admin))
        returned = client.post(
            f"/api/v1/remittances/{remittance_id}/import-returns",
            json=[{"receipt_number": receipt.receipt_number, "reason": "MS03"}],
            cookies=_auth_cookie(admin),
        )
        assert returned.status_code == 200
        db.refresh(receipt)
        assert receipt.status == "returned"
        return admin, receipt, remittance_id

    def test_reemitting_releases_the_receipt_from_its_batch(self, client, db):
        admin, receipt, remittance_id = self._returned_receipt(client, db, "rem-ret1")

        resp = client.post(f"/api/v1/receipts/{receipt.id}/reemit", cookies=_auth_cookie(admin))
        assert resp.status_code == 200

        db.refresh(receipt)
        assert receipt.remittance_id is None

    def test_a_reemitted_receipt_goes_into_a_new_batch(self, client, db):
        admin, receipt, _ = self._returned_receipt(client, db, "rem-ret2")

        client.post(f"/api/v1/receipts/{receipt.id}/reemit", cookies=_auth_cookie(admin))
        client.post(f"/api/v1/receipts/{receipt.id}/emit", cookies=_auth_cookie(admin))

        resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [receipt.id], "due_date": "2026-06-01"},
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 201, resp.json()
        assert resp.json()["receipt_count"] == 1

    def test_the_submitted_batch_keeps_what_it_collected(self, client, db):
        """The history is the batch's own totals plus the stored pain.008, not the link."""
        admin, receipt, remittance_id = self._returned_receipt(client, db, "rem-ret3")
        client.post(f"/api/v1/receipts/{receipt.id}/reemit", cookies=_auth_cookie(admin))

        resp = client.get(f"/api/v1/remittances/{remittance_id}", cookies=_auth_cookie(admin))
        assert resp.status_code == 200
        assert resp.json()["receipt_count"] == 1
        assert float(resp.json()["total_amount"]) == 60.50


class TestEligibleReceipts:
    """The picker asks the API what can be batched instead of deciding itself."""

    def test_an_emitted_receipt_with_a_mandate_is_offered(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-el1")
        member, _ = _create_member_with_mandate(db, suffix="rem-el1")
        receipt = _create_receipt(db, member.id, admin.id, suffix="rem-el1-01")

        resp = client.get("/api/v1/remittances/eligible-receipts", cookies=_auth_cookie(admin))
        assert resp.status_code == 200
        assert receipt.id in [r["id"] for r in resp.json()["items"]]

    def test_an_overdue_receipt_is_offered(self, client, db):
        """The dialog's own text offers overdue receipts; they were never fetched."""
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-el2")
        member, _ = _create_member_with_mandate(db, suffix="rem-el2")
        receipt = _create_receipt(db, member.id, admin.id, suffix="rem-el2-01", status="overdue")

        resp = client.get("/api/v1/remittances/eligible-receipts", cookies=_auth_cookie(admin))
        assert receipt.id in [r["id"] for r in resp.json()["items"]]

    def test_a_member_without_a_mandate_is_not_offered(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-el3")
        person = Person(first_name="No", last_name="Mandate", email="el3-no-mandate@examplee6e3b1.com")
        db.add(person)
        db.flush()
        mtype = MembershipType(
            name="Standard-el3", slug="standard-el3", base_price=50.00, billing_frequency="monthly"
        )
        db.add(mtype)
        db.flush()
        member = Member(
            person_id=person.id, membership_type_id=mtype.id, member_number="M-el3", status="active"
        )
        db.add(member)
        db.flush()
        receipt = _create_receipt(db, member.id, admin.id, suffix="rem-el3-01")

        resp = client.get("/api/v1/remittances/eligible-receipts", cookies=_auth_cookie(admin))
        assert receipt.id not in [r["id"] for r in resp.json()["items"]]

    def test_a_receipt_already_in_a_batch_is_not_offered(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-el4")
        member, _ = _create_member_with_mandate(db, suffix="rem-el4")
        receipt = _create_receipt(db, member.id, admin.id, suffix="rem-el4-01")
        client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [receipt.id], "due_date": "2026-05-01"},
            cookies=_auth_cookie(admin),
        )

        resp = client.get("/api/v1/remittances/eligible-receipts", cookies=_auth_cookie(admin))
        assert receipt.id not in [r["id"] for r in resp.json()["items"]]

    def test_a_pending_receipt_is_not_offered(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-el5")
        member, _ = _create_member_with_mandate(db, suffix="rem-el5")
        receipt = _create_receipt(db, member.id, admin.id, suffix="rem-el5-01", status="pending")

        resp = client.get("/api/v1/remittances/eligible-receipts", cookies=_auth_cookie(admin))
        assert receipt.id not in [r["id"] for r in resp.json()["items"]]

    def test_it_is_not_read_as_a_remittance_id(self, client, db):
        """Declared above `/{remittance_id}`, or the path 422s as a bad integer."""
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-el6")

        resp = client.get("/api/v1/remittances/eligible-receipts", cookies=_auth_cookie(admin))
        assert resp.status_code == 200


class TestAmountsSerialiseAsNumbers:
    """A money field has to arrive as a number, not as a string.

    Both list handlers build their own response dict out of `model_dump()`ed
    rows, so the values in it are raw `Decimal`s. While they also declared
    `response_model=dict`, FastAPI re-serialised that dict through Pydantic,
    and Pydantic v2 renders a `Decimal` as a JSON *string* — so `total_amount`
    went out as "60.50" while the frontend type said `number`. The batch dialog
    called `.toFixed` on it and took the page down (#364).

    No test caught it because every assertion compared values rather than
    types, and `"60.50" == 60.5` is simply false in neither direction anyone
    was looking. These assert the JSON type.
    """

    def test_an_eligible_receipt_amount_is_a_number(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-num1")
        member, _ = _create_member_with_mandate(db, suffix="rem-num1")
        receipt = _create_receipt(db, member.id, admin.id, suffix="rem-num1-01")

        resp = client.get(
            "/api/v1/remittances/eligible-receipts", cookies=_auth_cookie(admin)
        )
        assert resp.status_code == 200
        item = next(r for r in resp.json()["items"] if r["id"] == receipt.id)
        assert isinstance(item["total_amount"], (int, float)), (
            f"total_amount is {type(item['total_amount']).__name__}: "
            f"{item['total_amount']!r}"
        )
        assert not isinstance(item["total_amount"], str)

    def test_a_remittance_total_is_a_number(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-num2")
        member, _ = _create_member_with_mandate(db, suffix="rem-num2")
        receipt = _create_receipt(db, member.id, admin.id, suffix="rem-num2-01")

        created = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [receipt.id], "due_date": "2026-12-01"},
            cookies=_auth_cookie(admin),
        )
        assert created.status_code in (200, 201), created.text

        resp = client.get("/api/v1/remittances/", cookies=_auth_cookie(admin))
        assert resp.status_code == 200
        assert resp.json()["items"], "expected at least one remittance"
        for item in resp.json()["items"]:
            assert not isinstance(item["total_amount"], str), (
                f"total_amount is a string: {item['total_amount']!r}"
            )


class TestMandateErrorsNameTheMember:
    """An error listing `[48]` is unresolvable from any screen."""

    def test_a_missing_mandate_is_reported_as_a_code_with_member_labels(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-lbl")
        person = Person(first_name="Carlos", last_name="Blanch", email="lbl-no-mandate@examplee6e3b1.com")
        db.add(person)
        db.flush()
        mtype = MembershipType(
            name="Standard-lbl", slug="standard-lbl", base_price=50.00, billing_frequency="monthly"
        )
        db.add(mtype)
        db.flush()
        member = Member(
            person_id=person.id, membership_type_id=mtype.id, member_number="D-0023", status="active"
        )
        db.add(member)
        db.flush()
        receipt = _create_receipt(db, member.id, admin.id, suffix="rem-lbl-01")

        resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [receipt.id], "due_date": "2026-05-01"},
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert detail["code"] == "members_without_mandate"
        assert detail["members"] == ["D-0023 Carlos Blanch"]


class TestEligibleReceiptCarriesItsMember:
    """The batch picker has to be able to say whose receipt a row is.

    Its `SOCIO` column rendered `—` on every row because this endpoint returned
    `member_id` and nothing else, so there was nothing to render (#379). This is
    the screen that decides whose bank account gets debited.
    """

    def test_an_eligible_receipt_names_its_member(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-who1")
        member, _ = _create_member_with_mandate(db, suffix="rem-who1")
        receipt = _create_receipt(db, member.id, admin.id, suffix="rem-who1-01")

        resp = client.get(
            "/api/v1/remittances/eligible-receipts", cookies=_auth_cookie(admin)
        )
        assert resp.status_code == 200
        item = next(r for r in resp.json()["items"] if r["id"] == receipt.id)

        assert item["member_number"] == member.member_number
        # A name an admin can find in the register, not an internal id.
        assert item["member_name"]
        assert str(member.id) != item["member_name"]
        person = db.query(Person).filter(Person.id == member.person_id).first()
        assert person.first_name in item["member_name"]
        assert person.last_name in item["member_name"]

    def test_the_picker_and_the_refusal_name_a_member_the_same_way(self, client, db):
        """`label_members` formats the no-mandate refusal; the picker should
        agree with it, or the same person reads as two people."""
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-who2")
        member, _ = _create_member_with_mandate(db, suffix="rem-who2")
        receipt = _create_receipt(db, member.id, admin.id, suffix="rem-who2-01")

        resp = client.get(
            "/api/v1/remittances/eligible-receipts", cookies=_auth_cookie(admin)
        )
        item = next(r for r in resp.json()["items"] if r["id"] == receipt.id)

        label = label_members(db, [member.id])[0]
        assert label == f"{item['member_number']} {item['member_name']}"
