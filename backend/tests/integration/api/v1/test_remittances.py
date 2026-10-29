"""Integration tests for remittance (SEPA batch) endpoints."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from app.core.clock import org_today
from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.billing.models import (
    Concept,
    Receipt,
    Remittance,
    RemittanceReceipt,
    SepaMandate,
)
from app.domains.billing.remittance_service import label_members
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


# The SEPA collection date has to be one the bank can still act on, so these
# fixtures cannot carry a literal that quietly moves into the past (#395).
# Two weeks out, so it stays a future collection date whichever side of
# midnight the organisation's timezone is on — see `org_today` below.
COLLECTION_DATE = (date.today() + timedelta(days=14)).isoformat()


def _create_user(db, role="admin", suffix="rem"):
    person = Person(first_name="Admin", last_name="User", email=f"{suffix}-{role}@examplee6e3b1.com")
    db.add(person)
    db.flush()
    user = User(
        party_id=person.party_id,
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
        party_id=person.party_id,
        membership_type_id=mtype.id,
        member_number=f"M-{suffix}",
        status="active",
    )
    db.add(member)
    db.flush()

    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    mandate = SepaMandate(
        party_id=member.party_id,
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


def _create_receipt(
    db, member_id, user_id, suffix="rem", status="emitted", base_amount=Decimal("50.00")
):
    """Create a receipt for a member (addressed to the member's party)."""
    party_id = db.query(Member.party_id).filter(Member.id == member_id).scalar()
    concept = Concept(
        name=f"Fee-{suffix}",
        code=f"fee-{suffix}",
        concept_type="membership",
        default_amount=50.00,
        vat_rate=21.00,
    )
    db.add(concept)
    db.flush()

    vat_amount = (base_amount * Decimal("0.21")).quantize(Decimal("0.01"))
    receipt = Receipt(
        receipt_number=f"FAC-2026-{suffix}",
        party_id=party_id,
        concept_id=concept.id,
        origin="membership",
        description=f"Monthly fee {suffix}",
        base_amount=base_amount,
        vat_rate=Decimal("21.00"),
        vat_amount=vat_amount,
        total_amount=base_amount + vat_amount,
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
            json={"receipt_ids": [r1.id], "due_date": COLLECTION_DATE},
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
            json={"receipt_ids": [r1.id], "due_date": COLLECTION_DATE},
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
        member = Member(party_id=person.party_id, membership_type_id=mtype.id, member_number="M-noman", status="active")
        db.add(member)
        db.flush()

        r1 = _create_receipt(db, member.id, admin.id, suffix="rem-c3-01")

        resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [r1.id], "due_date": COLLECTION_DATE},
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
            json={"receipt_ids": [r1.id], "due_date": COLLECTION_DATE},
            cookies=_auth_cookie(admin),
        )

        # Try to batch same receipt again
        resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [r1.id], "due_date": COLLECTION_DATE},
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
            json={"receipt_ids": [r1.id], "due_date": COLLECTION_DATE},
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
                json={"receipt_ids": [receipt.id], "due_date": COLLECTION_DATE},
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
            json={"receipt_ids": [r1.id], "due_date": COLLECTION_DATE},
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
            json={"receipt_ids": [r1.id], "due_date": COLLECTION_DATE},
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
                "due_date": COLLECTION_DATE,
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
            json={"receipt_ids": [r1.id], "due_date": COLLECTION_DATE},
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
            json={"receipt_ids": [r1.id], "due_date": COLLECTION_DATE},
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
            json={"receipt_ids": [r1.id], "due_date": COLLECTION_DATE},
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
            json={"receipt_ids": [r1.id], "due_date": COLLECTION_DATE},
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
        assert result["returned"] == [receipt_number]
        assert result["already_returned"] == []
        assert result["ignored"] == []
        assert result["duplicate"] == []
        assert result["not_in_batch"] == []
        assert result["not_found"] == []

    def test_import_returns_not_found(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-ret2")
        m1, _ = _create_member_with_mandate(db, suffix="rem-ret2")
        r1 = _create_receipt(db, m1.id, admin.id, suffix="rem-ret2-01")

        create_resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [r1.id], "due_date": COLLECTION_DATE},
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
        assert resp.json()["not_found"] == ["FAKE-0000"]
        assert resp.json()["returned"] == []


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
            json={"receipt_ids": [r1.id], "due_date": COLLECTION_DATE},
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

        # Import returns (-> processed). A real return, because an empty array
        # is the absence of an answer and no longer moves the batch (#398).
        resp = client.post(
            f"/api/v1/remittances/{rem_id}/import-returns",
            json=[{"receipt_number": r1.receipt_number, "reason": "Insufficient funds"}],
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
            json={"receipt_ids": [r1.id], "due_date": COLLECTION_DATE},
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
            json={"receipt_ids": [r1.id], "due_date": COLLECTION_DATE},
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
            json={"receipt_ids": [r1.id], "due_date": COLLECTION_DATE},
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
            json={"receipt_ids": [1], "due_date": COLLECTION_DATE},
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

    def _submitted_remittance(self, client, admin, receipt_ids, due_date=COLLECTION_DATE):
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
            # The batch's own collection date, not the day it was closed.
            assert receipt.payment_date == date.fromisoformat(COLLECTION_DATE)

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
            json={"receipt_ids": [receipt.id], "due_date": COLLECTION_DATE},
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
            json={"receipt_ids": [receipt.id], "due_date": COLLECTION_DATE},
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


class TestASentBatchStillNamesWhatItSent:
    """A returned receipt leaves its batch to be collected again (#343), so the
    batch's `receipt_count` was the only record that it ever carried it — a
    number with no names in it. The admin could see that two receipts went to
    the bank and one is listed, with nothing saying which one came back or why
    (#402). `remittance_receipts` keeps that membership after the link is gone.
    """

    def _sent_batch_of_two(self, client, db, suffix):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix=suffix)
        member, _ = _create_member_with_mandate(db, suffix=suffix)
        kept = _create_receipt(db, member.id, admin.id, suffix=f"{suffix}-keep")
        returned = _create_receipt(db, member.id, admin.id, suffix=f"{suffix}-ret")

        created = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [kept.id, returned.id], "due_date": COLLECTION_DATE},
            cookies=_auth_cookie(admin),
        )
        assert created.status_code == 201, created.json()
        rid = created.json()["id"]

        client.post(f"/api/v1/remittances/{rid}/generate-xml", cookies=_auth_cookie(admin))
        client.post(f"/api/v1/remittances/{rid}/mark-submitted", cookies=_auth_cookie(admin))
        imported = client.post(
            f"/api/v1/remittances/{rid}/import-returns",
            json=[{"receipt_number": returned.receipt_number, "reason": "MS03"}],
            cookies=_auth_cookie(admin),
        )
        assert imported.status_code == 200
        return admin, kept, returned, rid

    def test_building_a_batch_records_every_receipt_it_carries(self, client, db):
        admin, kept, returned, rid = self._sent_batch_of_two(client, db, "rem-hist1")

        rows = (
            db.query(RemittanceReceipt)
            .filter(RemittanceReceipt.remittance_id == rid)
            .all()
        )
        assert {r.receipt_id for r in rows} == {kept.id, returned.id}
        assert all(r.released_at is None for r in rows)
        assert all(r.amount_sent == Decimal("60.50") for r in rows)

    def test_a_reemitted_receipt_is_still_listed_by_the_batch(self, client, db):
        admin, kept, returned, rid = self._sent_batch_of_two(client, db, "rem-hist2")
        client.post(f"/api/v1/receipts/{returned.id}/reemit", cookies=_auth_cookie(admin))

        resp = client.get(f"/api/v1/remittances/{rid}", cookies=_auth_cookie(admin))
        assert resp.status_code == 200
        numbers = [r["receipt_number"] for r in resp.json()["receipts"]]
        assert numbers == sorted([kept.receipt_number, returned.receipt_number])

    def test_the_released_line_says_when_and_why_it_left(self, client, db):
        admin, kept, returned, rid = self._sent_batch_of_two(client, db, "rem-hist3")
        client.post(f"/api/v1/receipts/{returned.id}/reemit", cookies=_auth_cookie(admin))

        resp = client.get(f"/api/v1/remittances/{rid}", cookies=_auth_cookie(admin))
        rows = {r["receipt_number"]: r for r in resp.json()["receipts"]}

        left = rows[returned.receipt_number]
        assert left["release_reason"] == "reemitted"
        assert left["released_at"] is not None
        # The status the admin needs is the one it has now: a re-emitted receipt
        # is `pending` and has to be emitted again before it can be collected.
        assert left["status"] == "pending"

        stayed = rows[kept.receipt_number]
        assert stayed["release_reason"] is None
        assert stayed["released_at"] is None

    def test_the_line_carries_what_the_batch_sent_for_it(self, client, db):
        """`total_amount` is the receipt's figure now; `amount_sent` is the one
        the bank was asked for, and a reissue can move the first."""
        admin, kept, returned, rid = self._sent_batch_of_two(client, db, "rem-hist4")
        client.post(f"/api/v1/receipts/{returned.id}/reemit", cookies=_auth_cookie(admin))

        db.refresh(returned)
        returned.total_amount = Decimal("12.25")
        db.flush()

        resp = client.get(f"/api/v1/remittances/{rid}", cookies=_auth_cookie(admin))
        row = next(
            r for r in resp.json()["receipts"]
            if r["receipt_number"] == returned.receipt_number
        )
        assert float(row["amount_sent"]) == 60.50
        assert float(row["total_amount"]) == 12.25

    def test_the_counters_still_describe_what_went_to_the_bank(self, client, db):
        """The list grows back to two; the counters were never the thing at
        fault and must not move."""
        admin, kept, returned, rid = self._sent_batch_of_two(client, db, "rem-hist5")
        client.post(f"/api/v1/receipts/{returned.id}/reemit", cookies=_auth_cookie(admin))

        body = client.get(f"/api/v1/remittances/{rid}", cookies=_auth_cookie(admin)).json()
        assert body["receipt_count"] == 2
        assert float(body["total_amount"]) == 121.00
        assert len(body["receipts"]) == 2

    def test_a_batch_still_being_assembled_lists_only_what_it_holds(self, client, db):
        """The other half of the rule: a receipt released from an open batch was
        taken out of the selection and the file will not carry it, so listing it
        would contradict the counters, which are recounted."""
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-hist6")
        member, _ = _create_member_with_mandate(db, suffix="rem-hist6")
        kept = _create_receipt(db, member.id, admin.id, suffix="rem-hist6-keep")
        dropped = _create_receipt(db, member.id, admin.id, suffix="rem-hist6-drop")

        created = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [kept.id, dropped.id], "due_date": COLLECTION_DATE},
            cookies=_auth_cookie(admin),
        )
        rid = created.json()["id"]

        cancelled = client.post(
            f"/api/v1/receipts/{dropped.id}/cancel", cookies=_auth_cookie(admin)
        )
        assert cancelled.status_code == 200, cancelled.json()

        body = client.get(f"/api/v1/remittances/{rid}", cookies=_auth_cookie(admin)).json()
        assert [r["receipt_number"] for r in body["receipts"]] == [kept.receipt_number]
        assert body["receipt_count"] == 1

        # The history row is still written — the batch did hold it, and the
        # reason is recorded even though this screen does not show it.
        row = (
            db.query(RemittanceReceipt)
            .filter(
                RemittanceReceipt.remittance_id == rid,
                RemittanceReceipt.receipt_id == dropped.id,
            )
            .one()
        )
        assert row.release_reason == "cancelled"

    def test_a_batch_sent_before_the_table_existed_lists_its_links(self, client, db):
        """No history to read, so the current links are the only answer there
        is — the behaviour an upgraded installation keeps for its old batches."""
        admin, kept, returned, rid = self._sent_batch_of_two(client, db, "rem-hist7")
        db.query(RemittanceReceipt).filter(
            RemittanceReceipt.remittance_id == rid
        ).delete()
        db.flush()

        body = client.get(f"/api/v1/remittances/{rid}", cookies=_auth_cookie(admin)).json()
        assert [r["receipt_number"] for r in body["receipts"]] == sorted(
            [kept.receipt_number, returned.receipt_number]
        )
        assert all(r["amount_sent"] is None for r in body["receipts"])

    def test_cancelling_a_batch_records_why_its_receipts_left(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="rem-hist8")
        member, _ = _create_member_with_mandate(db, suffix="rem-hist8")
        receipt = _create_receipt(db, member.id, admin.id, suffix="rem-hist8-01")

        created = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [receipt.id], "due_date": COLLECTION_DATE},
            cookies=_auth_cookie(admin),
        )
        rid = created.json()["id"]
        cancelled = client.post(
            f"/api/v1/remittances/{rid}/cancel", cookies=_auth_cookie(admin)
        )
        assert cancelled.status_code == 200

        row = (
            db.query(RemittanceReceipt)
            .filter(RemittanceReceipt.remittance_id == rid)
            .one()
        )
        assert row.release_reason == "batch_cancelled"
        assert row.released_at is not None


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
            party_id=person.party_id, membership_type_id=mtype.id, member_number="M-el3", status="active"
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
            json={"receipt_ids": [receipt.id], "due_date": COLLECTION_DATE},
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
            json={"receipt_ids": [receipt.id], "due_date": COLLECTION_DATE},
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
            party_id=person.party_id, membership_type_id=mtype.id, member_number="D-0023", status="active"
        )
        db.add(member)
        db.flush()
        receipt = _create_receipt(db, member.id, admin.id, suffix="rem-lbl-01")

        resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [receipt.id], "due_date": COLLECTION_DATE},
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
        person = db.query(Person).filter(Person.party_id == member.party_id).first()
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

        label = label_members(db, [member.party_id])[0]
        assert label == f"{item['member_number']} {item['member_name']}"


class TestBatchedReceiptIntegrity:
    """A batch has to still describe reality by the time its file is built.

    The file is generated from `remittance_id` with no status filter, so before
    this a receipt cancelled or settled another way after batching was still
    collected — the member debited money they did not owe (#383) — and a receipt
    released from a batch left the file collecting less than the batch claimed
    (#384).
    """

    def _batch(self, client, db, suffix, count=2):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix=suffix)
        member, _ = _create_member_with_mandate(db, suffix=suffix)
        receipts = [
            _create_receipt(db, member.id, admin.id, suffix=f"{suffix}-{i}")
            for i in range(count)
        ]
        created = client.post(
            "/api/v1/remittances/",
            json={
                "receipt_ids": [r.id for r in receipts],
                "due_date": COLLECTION_DATE,
            },
            cookies=_auth_cookie(admin),
        )
        assert created.status_code == 201, created.text
        return admin, member, receipts, created.json()["id"]

    # --- #383: a receipt that stops being collectible leaves an open batch ---

    def test_cancelling_a_batched_receipt_takes_it_out_of_the_batch(self, client, db):
        admin, _, receipts, rem_id = self._batch(client, db, "integ-cancel")

        resp = client.post(
            f"/api/v1/receipts/{receipts[0].id}/cancel", cookies=_auth_cookie(admin)
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["remittance_id"] is None

        db.expire_all()
        remittance = db.query(Remittance).filter(Remittance.id == rem_id).first()
        assert remittance.receipt_count == 1
        assert Decimal(str(remittance.total_amount)) == Decimal("60.50")

    def test_a_cancelled_receipt_is_not_in_the_generated_file(self, client, db):
        """The assertion that matters: the bank must not be told to collect it."""
        admin, _, receipts, rem_id = self._batch(client, db, "integ-xml")
        cancelled, kept = receipts[0], receipts[1]

        client.post(
            f"/api/v1/receipts/{cancelled.id}/cancel", cookies=_auth_cookie(admin)
        )
        gen = client.post(
            f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin)
        )
        assert gen.status_code == 200, gen.text

        xml = client.get(
            f"/api/v1/remittances/{rem_id}/download-xml", cookies=_auth_cookie(admin)
        ).text
        assert cancelled.receipt_number not in xml
        assert kept.receipt_number in xml
        assert "<NbOfTxs>1</NbOfTxs>" in xml
        assert "<CtrlSum>60.50</CtrlSum>" in xml

    def test_paying_a_batched_receipt_by_hand_takes_it_out_of_the_batch(self, client, db):
        admin, _, receipts, rem_id = self._batch(client, db, "integ-pay")

        resp = client.post(
            f"/api/v1/receipts/{receipts[0].id}/pay",
            json={"payment_method": "cash"},
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["remittance_id"] is None
        assert resp.json()["status"] == "paid"

        db.expire_all()
        remittance = db.query(Remittance).filter(Remittance.id == rem_id).first()
        assert remittance.receipt_count == 1

    # --- #383: once the file is with the bank, the answer is no ---

    def test_cancelling_is_refused_once_the_batch_has_been_submitted(self, client, db):
        admin, _, receipts, rem_id = self._batch(client, db, "integ-flight-c")
        client.post(
            f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin)
        )
        client.post(
            f"/api/v1/remittances/{rem_id}/mark-submitted", cookies=_auth_cookie(admin)
        )

        resp = client.post(
            f"/api/v1/receipts/{receipts[0].id}/cancel", cookies=_auth_cookie(admin)
        )
        assert resp.status_code == 409, resp.text
        detail = resp.json()["detail"]
        assert detail["code"] == "receipt_collection_in_flight"
        # Named so the admin can find the batch, not an internal id.
        assert detail["remittance_number"].startswith("REM-")

        db.expire_all()
        assert db.query(Receipt).filter(Receipt.id == receipts[0].id).first().status == "emitted"

    def test_paying_by_hand_is_refused_once_the_batch_has_been_submitted(self, client, db):
        admin, _, receipts, rem_id = self._batch(client, db, "integ-flight-p")
        client.post(
            f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin)
        )
        client.post(
            f"/api/v1/remittances/{rem_id}/mark-submitted", cookies=_auth_cookie(admin)
        )

        resp = client.post(
            f"/api/v1/receipts/{receipts[0].id}/pay",
            json={"payment_method": "cash"},
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["detail"]["code"] == "receipt_collection_in_flight"

    def test_closing_the_batch_still_settles_its_own_receipts(self, client, db):
        """The guard must not block the batch paying its receipts (close calls
        the same `mark_receipt_paid`), or a collected batch could never settle."""
        admin, _, receipts, rem_id = self._batch(client, db, "integ-close")
        client.post(
            f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin)
        )
        client.post(
            f"/api/v1/remittances/{rem_id}/mark-submitted", cookies=_auth_cookie(admin)
        )

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/close", cookies=_auth_cookie(admin)
        )
        assert resp.status_code == 200, resp.text

        db.expire_all()
        for r in receipts:
            row = db.query(Receipt).filter(Receipt.id == r.id).first()
            assert row.status == "paid"
            # Still linked: the batch is the record of what collected it.
            assert row.remittance_id == rem_id

    # --- #384: the file never collects less than the batch says ---

    def test_reemitting_from_an_open_batch_recounts_it(self, client, db):
        admin, _, receipts, rem_id = self._batch(client, db, "integ-recount")

        client.post(
            f"/api/v1/receipts/{receipts[0].id}/return",
            json={"return_reason": "Insufficient funds"},
            cookies=_auth_cookie(admin),
        )
        client.post(
            f"/api/v1/receipts/{receipts[0].id}/reemit", cookies=_auth_cookie(admin)
        )

        db.expire_all()
        remittance = db.query(Remittance).filter(Remittance.id == rem_id).first()
        assert remittance.receipt_count == 1
        assert Decimal(str(remittance.total_amount)) == Decimal("60.50")

        # And the file it produces agrees with it.
        gen = client.post(
            f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin)
        )
        assert gen.status_code == 200, gen.text
        xml = client.get(
            f"/api/v1/remittances/{rem_id}/download-xml", cookies=_auth_cookie(admin)
        ).text
        assert "<NbOfTxs>1</NbOfTxs>" in xml
        assert "<CtrlSum>60.50</CtrlSum>" in xml

    def test_generation_refuses_when_the_batch_is_out_of_step(self, client, db):
        """The invariant guard. Everything that releases a receipt recounts, so
        this cannot happen through the API — it is here so a future path that
        forgets cannot produce a file the bank would act on."""
        admin, _, receipts, rem_id = self._batch(client, db, "integ-outofstep")

        # Force the divergence the guard exists for.
        db.query(Receipt).filter(Receipt.id == receipts[0].id).update(
            {"remittance_id": None}
        )
        db.commit()

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin)
        )
        assert resp.status_code == 409, resp.text
        detail = resp.json()["detail"]
        assert detail["code"] == "remittance_out_of_step"
        assert detail["stored_count"] == 2
        assert detail["live_count"] == 1

    def test_a_submitted_batch_keeps_its_record_when_a_receipt_is_reemitted(
        self, client, db
    ):
        """#343's cycle, and the deliberate asymmetry: a batch that has gone to
        the bank keeps its own counters as the record of what it collected."""
        admin, _, receipts, rem_id = self._batch(client, db, "integ-frozen")
        client.post(
            f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin)
        )
        client.post(
            f"/api/v1/remittances/{rem_id}/mark-submitted", cookies=_auth_cookie(admin)
        )
        client.post(
            f"/api/v1/remittances/{rem_id}/import-returns",
            json=[{"receipt_number": receipts[0].receipt_number, "reason": "Insufficient funds"}],
            cookies=_auth_cookie(admin),
        )
        reemit = client.post(
            f"/api/v1/receipts/{receipts[0].id}/reemit", cookies=_auth_cookie(admin)
        )
        assert reemit.status_code == 200, reemit.text
        assert reemit.json()["remittance_id"] is None

        db.expire_all()
        remittance = db.query(Remittance).filter(Remittance.id == rem_id).first()
        assert remittance.receipt_count == 2
        assert Decimal(str(remittance.total_amount)) == Decimal("121.00")


class TestReturnImportShape:
    """The body's entries are validated, not just the fact that it is a list.

    `import_returns_endpoint` read the body off the request and checked only
    `isinstance(..., list)`, then called `.get` on each element — so an array of
    plain receipt numbers, which is the obvious guess for "return data" and what
    a bank's own export most resembles, came back as a 500 with nothing naming
    the problem (#396).
    """

    def _submitted(self, client, db, suffix):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix=suffix)
        member, _ = _create_member_with_mandate(db, suffix=suffix)
        receipt = _create_receipt(db, member.id, admin.id, suffix=f"{suffix}-01")
        number = receipt.receipt_number
        created = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [receipt.id], "due_date": COLLECTION_DATE},
            cookies=_auth_cookie(admin),
        )
        rem_id = created.json()["id"]
        client.post(f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin))
        client.post(f"/api/v1/remittances/{rem_id}/mark-submitted", cookies=_auth_cookie(admin))
        return admin, rem_id, number

    def test_an_array_of_bare_receipt_numbers_is_refused_not_crashed(self, client, db):
        admin, rem_id, number = self._submitted(client, db, "ret-shape1")

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/import-returns",
            json=[number],
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 422, resp.text
        # The index is the point: a 50-line paste needs to say which line.
        assert any(0 in item["loc"] for item in resp.json()["detail"])

    def test_a_null_entry_is_refused_not_crashed(self, client, db):
        admin, rem_id, _ = self._submitted(client, db, "ret-shape2")

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/import-returns",
            json=[None],
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 422, resp.text

    def test_an_entry_without_a_receipt_number_is_refused(self, client, db):
        admin, rem_id, _ = self._submitted(client, db, "ret-shape3")

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/import-returns",
            json=[{"reason": "Insufficient funds"}],
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 422, resp.text

    def test_a_body_that_is_not_a_list_is_still_refused(self, client, db):
        admin, rem_id, number = self._submitted(client, db, "ret-shape4")

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/import-returns",
            json={"receipt_number": number},
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 422, resp.text

    def test_the_reason_is_optional(self, client, db):
        admin, rem_id, number = self._submitted(client, db, "ret-shape5")

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/import-returns",
            json=[{"receipt_number": number}],
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["returned"] == [number]
        receipt = db.query(Receipt).filter(Receipt.receipt_number == number).first()
        db.refresh(receipt)
        assert receipt.return_reason == "Returned by bank"


class TestReturnImportReportsOutcomes:
    """What the import says happened, rather than how many entries it matched.

    `processed` counted every recognised receipt whether or not anything
    changed, so three different outcomes read identically — and a return
    landing on an already-paid receipt read as handled while doing nothing at
    all (#391).
    """

    def _batch(self, client, db, suffix, count=2):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix=suffix)
        member, _ = _create_member_with_mandate(db, suffix=suffix)
        receipts = [
            _create_receipt(db, member.id, admin.id, suffix=f"{suffix}-{i:02d}")
            for i in range(1, count + 1)
        ]
        created = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [r.id for r in receipts], "due_date": COLLECTION_DATE},
            cookies=_auth_cookie(admin),
        )
        assert created.status_code == 201, created.text
        rem_id = created.json()["id"]
        client.post(f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin))
        client.post(f"/api/v1/remittances/{rem_id}/mark-submitted", cookies=_auth_cookie(admin))
        return admin, receipts, rem_id

    def test_a_return_against_a_paid_receipt_refuses_the_whole_import(self, client, db):
        """The bank taking money back that memship says it collected is a
        contradiction for someone to resolve, not a line in a summary.

        Reachable without anything exotic: a member paying by card while the
        direct debit is in flight has the provider webhook mark the receipt
        paid, and webhooks are exempt from the in-flight guard (#383) because a
        webhook means the money really did move.
        """
        admin, receipts, rem_id = self._batch(client, db, "ret-paid")
        paid, bounced = receipts
        paid.status = "paid"
        paid.payment_date = date.today()
        db.flush()

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/import-returns",
            json=[
                {"receipt_number": paid.receipt_number, "reason": "MS03"},
                {"receipt_number": bounced.receipt_number, "reason": "MS03"},
            ],
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 409, resp.text
        detail = resp.json()["detail"]
        assert detail["code"] == "return_against_paid_receipt"
        assert detail["receipts"] == [paid.receipt_number]
        # All-or-nothing: the other receipt must not have been returned behind
        # the refusal, or re-importing the corrected file would double up.
        db.expire_all()
        assert db.query(Receipt).filter(Receipt.id == bounced.id).first().status == "emitted"

    def test_a_receipt_the_batch_cannot_return_is_named_with_its_status(self, client, db):
        admin, receipts, rem_id = self._batch(client, db, "ret-ignored")
        cancelled, bounced = receipts
        cancelled.status = "cancelled"
        db.flush()

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/import-returns",
            json=[
                {"receipt_number": cancelled.receipt_number, "reason": "MS03"},
                {"receipt_number": bounced.receipt_number, "reason": "MS03"},
            ],
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 200, resp.text
        result = resp.json()
        assert result["returned"] == [bounced.receipt_number]
        assert result["ignored"] == [
            {"receipt_number": cancelled.receipt_number, "status": "cancelled"}
        ]

    def test_re_importing_the_same_file_reports_already_returned(self, client, db):
        admin, receipts, rem_id = self._batch(client, db, "ret-again", count=1)
        number = receipts[0].receipt_number
        entries = [{"receipt_number": number, "reason": "MS03"}]

        first = client.post(
            f"/api/v1/remittances/{rem_id}/import-returns",
            json=entries,
            cookies=_auth_cookie(admin),
        )
        second = client.post(
            f"/api/v1/remittances/{rem_id}/import-returns",
            json=entries,
            cookies=_auth_cookie(admin),
        )

        assert first.json()["returned"] == [number]
        assert second.status_code == 200, second.text
        assert second.json()["returned"] == []
        assert second.json()["already_returned"] == [number]

    def test_a_line_repeated_in_the_file_is_counted_once(self, client, db):
        admin, receipts, rem_id = self._batch(client, db, "ret-dup", count=1)
        number = receipts[0].receipt_number

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/import-returns",
            json=[
                {"receipt_number": number, "reason": "MS03"},
                {"receipt_number": number, "reason": "MS03"},
            ],
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["returned"] == [number]
        assert resp.json()["duplicate"] == [number]

    def test_a_receipt_from_another_batch_says_which_batch(self, client, db):
        """Calling a real receipt number "not found" implied it was unknown.

        What is wrong is that it is somewhere else, and naming where is the
        answer the operator can act on.
        """
        admin, receipts, rem_id = self._batch(client, db, "ret-other", count=1)
        other_member, _ = _create_member_with_mandate(db, suffix="ret-other-b")
        stranger = _create_receipt(db, other_member.id, admin.id, suffix="ret-other-b-01")
        other = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [stranger.id], "due_date": COLLECTION_DATE},
            cookies=_auth_cookie(admin),
        )
        other_number = other.json()["remittance_number"]

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/import-returns",
            json=[{"receipt_number": stranger.receipt_number, "reason": "MS03"}],
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["not_in_batch"] == [
            {
                "receipt_number": stranger.receipt_number,
                "remittance_number": other_number,
            }
        ]
        assert resp.json()["not_found"] == []

    def test_an_unknown_number_is_still_not_found(self, client, db):
        admin, _, rem_id = self._batch(client, db, "ret-unknown", count=1)

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/import-returns",
            json=[{"receipt_number": "FAC-9999-9999", "reason": "MS03"}],
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["not_found"] == ["FAC-9999-9999"]
        assert resp.json()["not_in_batch"] == []


class TestZeroAmountReceiptsStayOutOfBatches:
    """A direct debit for zero collects nothing, and `sepaxml` cannot write it.

    Nothing about a 0,00 € receipt is malformed — `base_amount` is `ge=0` by
    design, and a fee fully covered by a discount lands there. Every gate on the
    way to the batch passed it, and the file generation then died on a bare
    `ValueError` from inside `sepaxml`, which reached the admin as a 500 with
    nothing naming the receipt (#392).
    """

    def _setup(self, client, db, suffix):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix=suffix)
        member, _ = _create_member_with_mandate(db, suffix=suffix)
        free = _create_receipt(
            db, member.id, admin.id, suffix=f"{suffix}-free", base_amount=Decimal("0.00")
        )
        assert Decimal(str(free.total_amount)) == Decimal("0.00")
        return admin, member, free

    def test_the_batch_picker_does_not_offer_it(self, client, db):
        admin, member, free = self._setup(client, db, "zero-pick")
        payable = _create_receipt(db, member.id, admin.id, suffix="zero-pick-02")

        resp = client.get("/api/v1/remittances/eligible-receipts", cookies=_auth_cookie(admin))

        assert resp.status_code == 200, resp.text
        offered = {item["receipt_number"] for item in resp.json()["items"]}
        assert payable.receipt_number in offered
        assert free.receipt_number not in offered

    def test_creating_a_batch_with_one_names_the_receipt(self, client, db):
        admin, _, free = self._setup(client, db, "zero-create")

        resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [free.id], "due_date": COLLECTION_DATE},
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 400, resp.text
        assert any(free.receipt_number in line for line in resp.json()["detail"])

    def test_a_batch_that_already_holds_one_refuses_to_build_the_file(self, client, db):
        """A batch created before the gates existed is still out there.

        The refusal has to name the receipt, because `sepaxml`'s own
        `ValueError` on the empty amount says nothing about which one.
        """
        admin, member, free = self._setup(client, db, "zero-legacy")
        payable = _create_receipt(db, member.id, admin.id, suffix="zero-legacy-02")
        created = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [payable.id], "due_date": COLLECTION_DATE},
            cookies=_auth_cookie(admin),
        )
        rem_id = created.json()["id"]

        # Put the zero-amount receipt in by hand, the way a batch created before
        # the eligibility gate holds one. The stored total is unchanged because
        # zero adds nothing, so the reconciliation guard (#384) stays quiet and
        # this is the check under test.
        free.remittance_id = rem_id
        remittance = db.query(Remittance).filter(Remittance.id == rem_id).first()
        remittance.receipt_count = 2
        db.flush()

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin)
        )

        assert resp.status_code == 400, resp.text
        detail = resp.json()["detail"]
        assert detail["code"] == "receipts_without_amount"
        assert detail["receipts"] == [free.receipt_number]
        assert detail["remittance_number"] == remittance.remittance_number


class TestCollectionDateMustBeCollectable:
    """The SEPA collection date, checked (#395).

    Nothing checked it: a batch dated 2020-01-05 was created and generated a
    file carrying `<ReqdColltnDt>2020-01-05</ReqdColltnDt>`, which the bank
    rejects whole.
    """

    def _receipt(self, client, db, suffix):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix=suffix)
        member, _ = _create_member_with_mandate(db, suffix=suffix)
        return admin, _create_receipt(db, member.id, admin.id, suffix=f"{suffix}-01")

    def test_a_batch_cannot_be_created_for_a_date_that_has_passed(self, client, db):
        admin, receipt = self._receipt(client, db, "date-past")

        resp = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [receipt.id], "due_date": "2020-01-05"},
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 400, resp.text
        assert resp.json()["detail"]["code"] == "collection_date_in_past"
        assert resp.json()["detail"]["due_date"] == "2020-01-05"

    def test_today_is_accepted(self, client, db):
        """Only the past is refused. A same-day collection is the bank's call,
        and a lead time memship invented would refuse dates that are fine."""
        admin, receipt = self._receipt(client, db, "date-today")

        resp = client.post(
            "/api/v1/remittances/",
            json={
                "receipt_ids": [receipt.id],
                # The organisation's today, not the runner's: CI is UTC and the
                # club is Europe/Madrid, so after 22:00 UTC they are different
                # days and this assertion would be about the wrong one.
                "due_date": org_today(db).isoformat(),
            },
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 201, resp.text

    def test_a_batch_left_until_its_date_has_passed_will_not_build_a_file(self, client, db):
        admin, receipt = self._receipt(client, db, "date-stale")
        created = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [receipt.id], "due_date": COLLECTION_DATE},
            cookies=_auth_cookie(admin),
        )
        rem_id = created.json()["id"]

        # The batch sat unsent until its collection date went by.
        remittance = db.query(Remittance).filter(Remittance.id == rem_id).first()
        remittance.due_date = org_today(db) - timedelta(days=1)
        db.flush()

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin)
        )

        assert resp.status_code == 400, resp.text
        assert resp.json()["detail"]["code"] == "collection_date_in_past"


class TestAFileOnlyStandsWhileTheBatchDoes:
    """Download and *mark submitted* had no opinion about the batch's state.

    A cancelled batch still handed out the file it once generated, whose
    receipts were by then back in circulation; and a batch whose regeneration
    was correctly refused still offered the stale file beside a working *mark
    submitted* button (#397).
    """

    def _ready_batch(self, client, db, suffix):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix=suffix)
        member, _ = _create_member_with_mandate(db, suffix=suffix)
        receipt = _create_receipt(db, member.id, admin.id, suffix=f"{suffix}-01")
        created = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [receipt.id], "due_date": COLLECTION_DATE},
            cookies=_auth_cookie(admin),
        )
        rem_id = created.json()["id"]
        generated = client.post(
            f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin)
        )
        assert generated.status_code == 200, generated.text
        return admin, member, receipt, rem_id

    def test_a_ready_batch_still_serves_its_file(self, client, db):
        admin, _, _, rem_id = self._ready_batch(client, db, "file-ready")

        resp = client.get(
            f"/api/v1/remittances/{rem_id}/download-xml", cookies=_auth_cookie(admin)
        )

        assert resp.status_code == 200, resp.text
        assert b"<ReqdColltnDt>" in resp.content

    def test_a_cancelled_batch_does_not(self, client, db):
        admin, _, _, rem_id = self._ready_batch(client, db, "file-cancelled")
        cancelled = client.post(
            f"/api/v1/remittances/{rem_id}/cancel", cookies=_auth_cookie(admin)
        )
        assert cancelled.status_code == 200, cancelled.text

        resp = client.get(
            f"/api/v1/remittances/{rem_id}/download-xml", cookies=_auth_cookie(admin)
        )

        assert resp.status_code == 409, resp.text
        assert resp.json()["detail"]["code"] == "remittance_file_withdrawn"
        assert resp.json()["detail"]["status"] == "cancelled"

    def test_a_batch_whose_mandate_went_away_cannot_be_marked_submitted(self, client, db):
        """The sharper half: generation refuses, so the file on disk is the
        previous one — and saying it went to the bank must refuse too."""
        admin, member, _, rem_id = self._ready_batch(client, db, "file-nomandate")
        for mandate in db.query(SepaMandate).filter(SepaMandate.party_id == member.party_id):
            mandate.status = "cancelled"
        db.flush()

        # Regeneration refuses before it gets as far as the mandate, because
        # the file already exists (#394) — either way the file on disk is the
        # previous one, which is what makes marking it submitted a lie.
        regenerate = client.post(
            f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin)
        )
        assert regenerate.status_code == 409, regenerate.text
        assert regenerate.json()["detail"]["code"] == "remittance_file_already_generated"

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/mark-submitted", cookies=_auth_cookie(admin)
        )

        assert resp.status_code == 400, resp.text
        assert resp.json()["detail"]["code"] == "sepa_mandate_cancelled"

    def test_a_batch_out_of_step_with_its_receipts_cannot_be_marked_submitted(self, client, db):
        admin, _, receipt, rem_id = self._ready_batch(client, db, "file-outofstep")
        remittance = db.query(Remittance).filter(Remittance.id == rem_id).first()
        remittance.receipt_count = 7
        db.flush()

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/mark-submitted", cookies=_auth_cookie(admin)
        )

        assert resp.status_code == 409, resp.text
        assert resp.json()["detail"]["code"] == "remittance_out_of_step"

    def test_a_batch_whose_date_went_by_cannot_be_marked_submitted(self, client, db):
        admin, _, _, rem_id = self._ready_batch(client, db, "file-datepast")
        remittance = db.query(Remittance).filter(Remittance.id == rem_id).first()
        remittance.due_date = org_today(db) - timedelta(days=1)
        db.flush()

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/mark-submitted", cookies=_auth_cookie(admin)
        )

        assert resp.status_code == 400, resp.text
        assert resp.json()["detail"]["code"] == "collection_date_in_past"


class TestOneActiveMandatePerMember:
    """A member has one account the club collects from (#394).

    Two active mandates were a normal save, and both selection sites then
    picked between them with "latest by `created_at`", no tie-break and no
    `ORDER BY` — `created_at` is a server default, so two mandates written in
    the same transaction share a timestamp and the winner was whichever row the
    query happened to return first.
    """

    def test_a_second_active_mandate_is_refused_and_names_the_first(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="one-mandate")
        member, mandate = _create_member_with_mandate(db, suffix="one-mandate")

        resp = client.post(
            "/api/v1/mandates/",
            json={
                "member_id": member.id,
                "debtor_name": "Test Member",
                "debtor_iban": "DE89370400440532013000",
                "mandate_type": "recurrent",
                "signature_method": "paper",
                "signed_at": date.today().isoformat(),
            },
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 409, resp.text
        detail = resp.json()["detail"]
        assert detail["code"] == "member_already_has_mandate"
        # Naming it is the point: the remedy is to cancel that one.
        assert detail["mandate_reference"] == mandate.mandate_reference

    def test_cancelling_the_first_lets_a_new_one_be_signed(self, client, db):
        """Changing bank account is routine — it must not be blocked, only
        made explicit."""
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="remandate")
        member, mandate = _create_member_with_mandate(db, suffix="remandate")

        cancelled = client.post(
            f"/api/v1/mandates/{mandate.id}/cancel", cookies=_auth_cookie(admin)
        )
        assert cancelled.status_code == 200, cancelled.text

        resp = client.post(
            "/api/v1/mandates/",
            json={
                "member_id": member.id,
                "debtor_name": "Test Member",
                "debtor_iban": "DE89370400440532013000",
                "mandate_type": "recurrent",
                "signature_method": "paper",
                "signed_at": date.today().isoformat(),
            },
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 201, resp.text
        assert resp.json()["debtor_iban"] == "DE89370400440532013000"

    def test_the_batch_and_the_file_agree_on_the_mandate(self, client, db):
        """The two selection sites read the same rule, so the account the batch
        was validated against is the account the file collects from."""
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="same-mandate")
        member, mandate = _create_member_with_mandate(db, suffix="same-mandate")
        receipt = _create_receipt(db, member.id, admin.id, suffix="same-mandate-01")

        created = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [receipt.id], "due_date": COLLECTION_DATE},
            cookies=_auth_cookie(admin),
        )
        rem_id = created.json()["id"]
        client.post(f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin))

        xml = client.get(
            f"/api/v1/remittances/{rem_id}/download-xml", cookies=_auth_cookie(admin)
        )
        assert xml.status_code == 200, xml.text
        assert mandate.mandate_reference.encode() in xml.content
        assert mandate.debtor_iban.encode() in xml.content


class TestAGeneratedFileIsNotOverwritten:
    """The file is the record of what went to the bank (#394).

    It was written under the remittance number with no versioning and no
    refusal, and generation is allowed from `draft` *or* `ready` — so a second
    generation replaced it with a different `MsgId`, and potentially a
    different mandate and debtor IBAN, under the same name.
    """

    def _generated(self, client, db, suffix):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix=suffix)
        member, _ = _create_member_with_mandate(db, suffix=suffix)
        receipt = _create_receipt(db, member.id, admin.id, suffix=f"{suffix}-01")
        created = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [receipt.id], "due_date": COLLECTION_DATE},
            cookies=_auth_cookie(admin),
        )
        rem_id = created.json()["id"]
        first = client.post(
            f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin)
        )
        assert first.status_code == 200, first.text
        # `generate-xml` answers with the remittance; the file itself comes
        # back from `download-xml`.
        stored = client.get(
            f"/api/v1/remittances/{rem_id}/download-xml", cookies=_auth_cookie(admin)
        )
        assert stored.status_code == 200, stored.text
        return admin, rem_id, stored.content

    def test_a_second_generation_is_refused(self, client, db):
        admin, rem_id, _ = self._generated(client, db, "nooverwrite")

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin)
        )

        assert resp.status_code == 409, resp.text
        assert resp.json()["detail"]["code"] == "remittance_file_already_generated"

    def test_the_first_file_is_still_what_downloads(self, client, db):
        admin, rem_id, generated = self._generated(client, db, "nooverwrite2")
        client.post(f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin))

        resp = client.get(
            f"/api/v1/remittances/{rem_id}/download-xml", cookies=_auth_cookie(admin)
        )

        assert resp.status_code == 200, resp.text
        assert resp.content == generated

    def test_cancelling_and_rebuilding_is_still_the_way_through(self, client, db):
        """The refusal has to leave a route, and this is the one the product
        already documents for a changed mandate."""
        admin, rem_id, _ = self._generated(client, db, "rebuild")
        cancelled = client.post(
            f"/api/v1/remittances/{rem_id}/cancel", cookies=_auth_cookie(admin)
        )
        assert cancelled.status_code == 200, cancelled.text

        receipt = db.query(Receipt).filter(Receipt.receipt_number == "FAC-2026-rebuild-01").first()
        db.refresh(receipt)
        assert receipt.remittance_id is None

        rebuilt = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [receipt.id], "due_date": COLLECTION_DATE},
            cookies=_auth_cookie(admin),
        )
        assert rebuilt.status_code == 201, rebuilt.text
        regenerated = client.post(
            f"/api/v1/remittances/{rebuilt.json()['id']}/generate-xml",
            cookies=_auth_cookie(admin),
        )
        assert regenerated.status_code == 200, regenerated.text


class TestAnEmptyImportIsNotAnAnswer:
    """`processed` is a one-way door, and an empty array is no information.

    The transition was applied after the loop whatever the loop did, so posting
    `[]` moved a batch from `submitted` to `processed` — a state it cannot come
    back from — on the strength of nothing (#398).
    """

    def _submitted(self, client, db, suffix):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix=suffix)
        member, _ = _create_member_with_mandate(db, suffix=suffix)
        receipt = _create_receipt(db, member.id, admin.id, suffix=f"{suffix}-01")
        created = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [receipt.id], "due_date": COLLECTION_DATE},
            cookies=_auth_cookie(admin),
        )
        rem_id = created.json()["id"]
        client.post(f"/api/v1/remittances/{rem_id}/generate-xml", cookies=_auth_cookie(admin))
        client.post(f"/api/v1/remittances/{rem_id}/mark-submitted", cookies=_auth_cookie(admin))
        return admin, rem_id

    def test_an_empty_array_is_refused(self, client, db):
        admin, rem_id = self._submitted(client, db, "empty-import")

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/import-returns",
            json=[],
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 422, resp.text
        remittance = db.query(Remittance).filter(Remittance.id == rem_id).first()
        db.refresh(remittance)
        assert remittance.status == "submitted"

    def test_a_file_naming_nothing_this_batch_holds_leaves_the_status_alone(self, client, db):
        admin, rem_id = self._submitted(client, db, "foreign-import")

        resp = client.post(
            f"/api/v1/remittances/{rem_id}/import-returns",
            json=[{"receipt_number": "FAC-9999-9999", "reason": "MS03"}],
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["not_found"] == ["FAC-9999-9999"]
        remittance = db.query(Remittance).filter(Remittance.id == rem_id).first()
        db.refresh(remittance)
        assert remittance.status == "submitted"


class TestACancelledBatchHoldsNothing:
    """The detail page rendered "Recibos 1 · Total 30,25 €" directly above
    "this batch has no receipts" — a stored counter over a live table (#398)."""

    def test_cancelling_recounts_the_batch(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="cancel-count")
        member, _ = _create_member_with_mandate(db, suffix="cancel-count")
        receipt = _create_receipt(db, member.id, admin.id, suffix="cancel-count-01")
        created = client.post(
            "/api/v1/remittances/",
            json={"receipt_ids": [receipt.id], "due_date": COLLECTION_DATE},
            cookies=_auth_cookie(admin),
        )
        rem_id = created.json()["id"]
        assert created.json()["receipt_count"] == 1

        resp = client.post(f"/api/v1/remittances/{rem_id}/cancel", cookies=_auth_cookie(admin))

        assert resp.status_code == 200, resp.text
        assert resp.json()["receipt_count"] == 0
        assert Decimal(str(resp.json()["total_amount"])) == Decimal("0")
