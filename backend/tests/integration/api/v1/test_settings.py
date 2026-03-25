"""Integration tests for organization settings endpoints."""

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Address, Person


def _create_user(db, role="super_admin", suffix="settings"):
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
    """Ensure organization_settings record exists."""
    existing = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not existing:
        org = OrganizationSettings(
            id=1,
            name="Test Organization",
            locale="es",
            timezone="Europe/Madrid",
            currency="EUR",
            date_format="DD/MM/YYYY",
        )
        db.add(org)
        db.flush()
    return db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()


class TestGetSettings:
    def test_get_settings_authenticated(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "member", "get-set")
        client.cookies.update(_auth_cookie(user))

        response = client.get("/api/v1/settings/")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["name"] == "Test Organization"
        assert data["locale"] == "es"

    def test_get_settings_unauthenticated(self, client):
        response = client.get("/api/v1/settings/")
        assert response.status_code in (401, 403)


class TestUpdateSettings:
    def test_update_settings_super_admin(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "super_admin", "upd-sa")
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            "/api/v1/settings/",
            json={"name": "Updated Club", "locale": "ca", "brand_color": "#3B82F6"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Club"
        assert data["locale"] == "ca"
        assert data["brand_color"] == "#3B82F6"

    def test_update_settings_admin_forbidden(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "admin", "upd-adm")
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            "/api/v1/settings/",
            json={"name": "Blocked"},
        )
        assert response.status_code == 403

    def test_update_settings_member_forbidden(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "member", "upd-mem")
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            "/api/v1/settings/",
            json={"name": "Blocked"},
        )
        assert response.status_code == 403

    def test_update_settings_partial(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "super_admin", "upd-partial")
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            "/api/v1/settings/",
            json={"phone": "+34 600 123 456"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["phone"] == "+34 600 123 456"
        assert data["name"] == "Test Organization"  # unchanged

    def test_update_invalid_locale(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "super_admin", "upd-invloc")
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            "/api/v1/settings/",
            json={"locale": "fr"},
        )
        assert response.status_code == 422

    def test_update_invalid_brand_color(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "super_admin", "upd-invclr")
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            "/api/v1/settings/",
            json={"brand_color": "not-a-color"},
        )
        assert response.status_code == 422


class TestBankingFields:
    def test_update_bank_details(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "super_admin", "bank1")
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            "/api/v1/settings/",
            json={
                "bank_name": "CaixaBank",
                "bank_iban": "ES9121000418450200051332",
                "bank_bic": "CAIXESBBXXX",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["bank_name"] == "CaixaBank"
        assert data["bank_iban"] == "ES9121000418450200051332"
        assert data["bank_bic"] == "CAIXESBBXXX"

    def test_update_invoice_series(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "super_admin", "inv1")
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            "/api/v1/settings/",
            json={"invoice_prefix": "FAC", "invoice_next_number": 100},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["invoice_prefix"] == "FAC"
        assert data["invoice_next_number"] == 100

    def test_invalid_iban_format(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "super_admin", "inv-iban")
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            "/api/v1/settings/",
            json={"bank_iban": "invalid-iban"},
        )
        assert response.status_code == 422

    def test_invalid_bic_format(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "super_admin", "inv-bic")
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            "/api/v1/settings/",
            json={"bank_bic": "XX"},
        )
        assert response.status_code == 422

    def test_bank_fields_in_get_response(self, client, db):
        org = _ensure_org_settings(db)
        org.bank_name = "BBVA"
        org.bank_iban = "ES7921000813610123456789"
        org.invoice_prefix = "REC"
        org.invoice_next_number = 50
        db.flush()

        user = _create_user(db, "member", "bank-get")
        client.cookies.update(_auth_cookie(user))

        response = client.get("/api/v1/settings/")
        assert response.status_code == 200
        data = response.json()
        assert data["bank_name"] == "BBVA"
        assert data["bank_iban"] == "ES7921000813610123456789"
        assert data["invoice_prefix"] == "REC"
        assert data["invoice_next_number"] == 50


class TestOrganizationAddress:
    def test_get_address_empty(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "member", "addr-empty")
        client.cookies.update(_auth_cookie(user))

        response = client.get("/api/v1/settings/address")
        assert response.status_code == 200
        assert response.json() is None

    def test_create_address(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "super_admin", "addr-create")
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            "/api/v1/settings/address",
            json={
                "address_line1": "Carrer Major 1",
                "city": "Barcelona",
                "state_province": "Barcelona",
                "postal_code": "08001",
                "country": "ES",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["address_line1"] == "Carrer Major 1"
        assert data["city"] == "Barcelona"
        assert data["postal_code"] == "08001"
        assert data["country"] == "ES"

    def test_update_existing_address(self, client, db):
        _ensure_org_settings(db)
        # Create an address first
        addr = Address(
            entity_type="organization",
            entity_id=1,
            address_line1="Old Street 1",
            city="Madrid",
            country="ES",
            is_primary=True,
        )
        db.add(addr)
        db.flush()

        user = _create_user(db, "super_admin", "addr-update")
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            "/api/v1/settings/address",
            json={
                "address_line1": "Carrer Nou 5",
                "city": "Girona",
                "postal_code": "17001",
                "country": "ES",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["address_line1"] == "Carrer Nou 5"
        assert data["city"] == "Girona"
        assert data["id"] == addr.id  # same record, updated

    def test_create_address_requires_super_admin(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "admin", "addr-rbac")
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            "/api/v1/settings/address",
            json={
                "address_line1": "Test Street",
                "city": "Test City",
                "country": "ES",
            },
        )
        assert response.status_code == 403

    def test_create_address_validation(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "super_admin", "addr-valid")
        client.cookies.update(_auth_cookie(user))

        # Missing required field (address_line1)
        response = client.put(
            "/api/v1/settings/address",
            json={"city": "Barcelona", "country": "ES"},
        )
        assert response.status_code == 422
