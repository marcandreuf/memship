"""Integration tests for organization settings endpoints."""

import pytest

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Address, Person


def _create_user(db, role="super_admin", suffix="settings"):
    person = Person(first_name="Test", last_name="User", email=f"{suffix}-{role}@examplee6e3b1.com")
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
        user = _create_user(db, "admin", "get-set")
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

    def test_update_settings_admin_allowed(self, client, db):
        """admin holds settings.write (unlike settings.integrations.write / roles.write,
        it isn't reserved to super_admin) — see ADMIN_SEED_KEYS."""
        _ensure_org_settings(db)
        user = _create_user(db, "admin", "upd-adm")
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            "/api/v1/settings/",
            json={"name": "Updated by Admin"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated by Admin"

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


class TestBookingRules:
    """`features` is free-form JSON, but the booking rules in it are read as
    integers by every availability, booking and cancellation request (#295)."""

    @pytest.mark.parametrize(
        "features",
        [
            {"booking_window_days": 0},
            {"booking_window_days": -5},
            {"booking_window_days": 366},
            {"booking_window_days": "14"},
            {"booking_window_days": 1.5},
            {"booking_window_days": True},
            {"booking_window_days": None},
            {"booking_cancellation_deadline_hours": -1},
            {"booking_cancellation_deadline_hours": "abc"},
            {"booking_cancellation_deadline_hours": 8761},
        ],
    )
    def test_invalid_booking_rule_rejected(self, client, db, features):
        org = _ensure_org_settings(db)
        org.features = {"bookings": True}
        db.flush()
        user = _create_user(db, "super_admin", "upd-bookrule")
        client.cookies.update(_auth_cookie(user))

        response = client.put("/api/v1/settings/", json={"features": features})

        assert response.status_code == 422
        db.refresh(org)
        assert org.features == {"bookings": True}

    @pytest.mark.parametrize(
        "features",
        [
            {"booking_window_days": 1, "booking_cancellation_deadline_hours": 0},
            {"booking_window_days": 365, "booking_cancellation_deadline_hours": 8760},
            {"bookings": False},
        ],
    )
    def test_valid_booking_rule_accepted(self, client, db, features):
        _ensure_org_settings(db)
        user = _create_user(db, "super_admin", "upd-bookok")
        client.cookies.update(_auth_cookie(user))

        response = client.put("/api/v1/settings/", json={"features": features})

        assert response.status_code == 200
        assert response.json()["features"] == features


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

        user = _create_user(db, "admin", "bank-get")
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
        user = _create_user(db, "admin", "addr-empty")
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

    def test_create_address_member_forbidden(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "member", "addr-rbac")
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


class TestFeaturesMerge:
    """`features` is a sparse update: the keys sent are written, the rest stay.

    Every flag the organization has lives in one JSONB column on one row, so a
    whole-column replace made two clients a lost update — each settings form
    posted back the snapshot its own browser had loaded, and the later save
    silently reverted the earlier one's flag. It surfaced as three member-card
    E2E tests failing under parallel load and passing alone (#314), and is
    reachable by two administrators with a settings tab each.
    """

    def test_absent_key_is_left_alone(self, client, db):
        org = _ensure_org_settings(db)
        org.features = {"bookings": True, "member_card": True}
        db.flush()
        user = _create_user(db, "super_admin", "feat-keep")
        client.cookies.update(_auth_cookie(user))

        response = client.put("/api/v1/settings/", json={"features": {"bookings": False}})

        assert response.status_code == 200
        db.refresh(org)
        # The flag nobody sent survives; the one that was sent is written.
        assert org.features["member_card"] is True
        assert org.features["bookings"] is False

    def test_a_flag_is_switched_off_by_sending_false(self, client, db):
        org = _ensure_org_settings(db)
        org.features = {"member_card": True}
        db.flush()
        user = _create_user(db, "super_admin", "feat-off")
        client.cookies.update(_auth_cookie(user))

        response = client.put("/api/v1/settings/", json={"features": {"member_card": False}})

        assert response.status_code == 200
        db.refresh(org)
        assert org.features["member_card"] is False

    def test_a_new_flag_is_added(self, client, db):
        org = _ensure_org_settings(db)
        org.features = {"bookings": True}
        db.flush()
        user = _create_user(db, "super_admin", "feat-add")
        client.cookies.update(_auth_cookie(user))

        response = client.put("/api/v1/settings/", json={"features": {"member_card": True}})

        assert response.status_code == 200
        db.refresh(org)
        assert org.features == {"bookings": True, "member_card": True}

    def test_a_stale_snapshot_cannot_revert_a_sibling_flag(self, client, db):
        """The #314 sequence, as a test.

        A second client holds a snapshot taken before another switched
        `member_card` on, then saves its own unrelated setting.
        """
        org = _ensure_org_settings(db)
        org.features = {"bookings": True}
        db.flush()
        stale_snapshot = dict(org.features)

        user = _create_user(db, "super_admin", "feat-stale")
        client.cookies.update(_auth_cookie(user))

        # Client A switches the card on.
        client.put("/api/v1/settings/", json={"features": {"member_card": True}})
        # Client B saves its own tab, posting back everything it loaded at t0.
        response = client.put("/api/v1/settings/", json={"features": stale_snapshot})

        assert response.status_code == 200
        db.refresh(org)
        assert org.features["member_card"] is True

    def test_other_json_columns_are_unaffected(self, client, db):
        """Only `features` merges; the rest of the payload still assigns."""
        org = _ensure_org_settings(db)
        org.features = {"bookings": True}
        db.flush()
        user = _create_user(db, "super_admin", "feat-other")
        client.cookies.update(_auth_cookie(user))

        response = client.put("/api/v1/settings/", json={"name": "Renamed Club"})

        assert response.status_code == 200
        db.refresh(org)
        assert org.name == "Renamed Club"
        assert org.features == {"bookings": True}
