"""Integration tests for member payment method endpoints."""

from datetime import date

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.billing.models import SepaMandate
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


def _setup(db, iban=None, payment_method=None):
    """Create org, membership type, member user with optional bank details."""
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(
            id=1, name="Club Test", locale="es", timezone="Europe/Madrid",
            currency="EUR", date_format="DD/MM/YYYY", invoice_prefix="FAC",
            invoice_next_number=1, invoice_annual_reset=True, default_vat_rate=21.00,
            creditor_id="ES12000B12345678", bank_iban="ES9121000418450200051332",
            bank_bic="CAIXESBBXXX",
        )
        db.add(org)
        db.flush()

    mt = db.query(MembershipType).first()
    if not mt:
        mt = MembershipType(name="Standard", slug="standard", base_price=100)
        db.add(mt)
        db.flush()

    person = Person(
        first_name="Test", last_name="Member", email="pm-member@test.com",
        bank_iban=iban, payment_method=payment_method,
    )
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id, email="pm-member@test.com",
        password_hash=hash_password("password123"),
        role="member", is_active=True,
    )
    db.add(user)
    db.flush()
    member = Member(
        person_id=person.id, user_id=user.id,
        membership_type_id=mt.id, member_number="PM-0001", status="active",
    )
    db.add(member)
    db.flush()
    return user, member


def _auth(user):
    return {"access_token": create_access_token(user.id, user.role)}


class TestGetPaymentMethod:
    def test_returns_empty_for_new_member(self, client, db):
        user, _ = _setup(db)
        db.commit()
        r = client.get("/api/v1/members/me/payment-method", cookies=_auth(user))
        assert r.status_code == 200
        data = r.json()
        assert data["payment_method"] is None
        assert data["bank_iban"] is None
        assert data["mandate_status"] == "none"
        assert data["warnings"] == []

    def test_returns_iban_and_mandate_info(self, client, db):
        user, member = _setup(db, iban="ES6621000418401234567891", payment_method="direct_debit")
        member.person.bank_bic = "CAIXESBBXXX"
        mandate = SepaMandate(
            member_id=member.id, mandate_reference="TEST-PM-001",
            creditor_id="ES12000B12345678", debtor_name="Test Member",
            debtor_iban="ES6621000418401234567891", status="active",
            signed_at=date(2026, 1, 1),
        )
        db.add(mandate)
        db.commit()
        r = client.get("/api/v1/members/me/payment-method", cookies=_auth(user))
        assert r.status_code == 200
        data = r.json()
        assert data["payment_method"] == "direct_debit"
        assert data["bank_iban"] == "ES6621000418401234567891"
        assert data["bank_iban_masked"] == "ES66 **** **** **** 7891"
        assert data["mandate_status"] == "active"
        assert data["mandate_reference"] == "TEST-PM-001"
        assert data["warnings"] == []

    def test_warnings_for_direct_debit_without_iban(self, client, db):
        user, _ = _setup(db, payment_method="direct_debit")
        db.commit()
        r = client.get("/api/v1/members/me/payment-method", cookies=_auth(user))
        data = r.json()
        assert "missing_iban" in data["warnings"]
        assert "no_active_mandate" in data["warnings"]

    def test_warning_for_missing_bic(self, client, db):
        user, _ = _setup(db, iban="ES6621000418401234567891", payment_method="direct_debit")
        db.commit()
        r = client.get("/api/v1/members/me/payment-method", cookies=_auth(user))
        data = r.json()
        assert "missing_bic" in data["warnings"]


class TestUpdatePaymentMethod:
    def test_update_payment_method(self, client, db):
        user, _ = _setup(db)
        db.commit()
        r = client.put("/api/v1/members/me/payment-method", cookies=_auth(user), json={
            "payment_method": "bank_transfer",
            "bank_iban": "ES7920385778983000760236",
            "bank_bic": "CAIXESBBXXX",
            "bank_holder_name": "Test Member",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["payment_method"] == "bank_transfer"
        assert data["bank_iban"] == "ES7920385778983000760236"
        assert data["bank_holder_name"] == "Test Member"

    def test_iban_normalized_uppercase(self, client, db):
        user, _ = _setup(db)
        db.commit()
        r = client.put("/api/v1/members/me/payment-method", cookies=_auth(user), json={
            "bank_iban": "es79 2038 5778 9830 0076 0236",
        })
        assert r.status_code == 200
        assert r.json()["bank_iban"] == "ES7920385778983000760236"

    def test_invalid_payment_method_rejected(self, client, db):
        user, _ = _setup(db)
        db.commit()
        r = client.put("/api/v1/members/me/payment-method", cookies=_auth(user), json={
            "payment_method": "bitcoin",
        })
        assert r.status_code == 422

    def test_set_direct_debit_with_warnings(self, client, db):
        user, _ = _setup(db)
        db.commit()
        r = client.put("/api/v1/members/me/payment-method", cookies=_auth(user), json={
            "payment_method": "direct_debit",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["payment_method"] == "direct_debit"
        assert "missing_iban" in data["warnings"]
        assert "no_active_mandate" in data["warnings"]

    def test_clear_iban(self, client, db):
        user, _ = _setup(db, iban="ES6621000418401234567891")
        db.commit()
        r = client.put("/api/v1/members/me/payment-method", cookies=_auth(user), json={
            "bank_iban": None,
        })
        assert r.status_code == 200
        assert r.json()["bank_iban"] is None


class TestPaymentMethodAuth:
    def test_unauthenticated_rejected(self, client, db):
        r = client.get("/api/v1/members/me/payment-method")
        assert r.status_code in (401, 403)

    def test_admin_can_access_own(self, client, db):
        """Admins also have a person, so they can access this endpoint."""
        org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
        if not org:
            org = OrganizationSettings(
                id=1, name="Club Test", locale="es", timezone="Europe/Madrid",
                currency="EUR", date_format="DD/MM/YYYY", invoice_prefix="FAC",
                invoice_next_number=1, invoice_annual_reset=True, default_vat_rate=21.00,
            )
            db.add(org)
            db.flush()
        person = Person(first_name="Admin", last_name="User", email="pm-admin@test.com")
        db.add(person)
        db.flush()
        user = User(
            person_id=person.id, email="pm-admin@test.com",
            password_hash=hash_password("password123"),
            role="admin", is_active=True,
        )
        db.add(user)
        db.commit()
        r = client.get("/api/v1/members/me/payment-method", cookies=_auth(user))
        assert r.status_code == 200
