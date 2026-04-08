"""Unit tests for v0.4.0 billing models and schemas — no DB required."""

from datetime import date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domains.billing.schemas import (
    MandateCreate,
    MandateUpdate,
    MandateResponse,
    RemittanceCreate,
    RemittanceResponse,
    RemittanceDetailResponse,
    PaymentProviderCreate,
    PaymentProviderUpdate,
    PaymentProviderResponse,
)
from app.domains.organizations.schemas import (
    OrganizationSettingsResponse,
    OrganizationSettingsUpdate,
)


# --- Helpers ---


def _valid_mandate_data(**overrides):
    base = {
        "member_id": 1,
        "debtor_name": "John Doe",
        "debtor_iban": "ES9121000418450200051332",
        "signed_at": "2026-04-01",
    }
    base.update(overrides)
    return base


def _valid_remittance_create(**overrides):
    base = {
        "receipt_ids": [1, 2, 3],
        "due_date": "2026-05-01",
    }
    base.update(overrides)
    return base


def _valid_provider_data(**overrides):
    base = {
        "provider_type": "sepa_direct_debit",
        "display_name": "SEPA Direct Debit",
    }
    base.update(overrides)
    return base


# --- MandateCreate ---


class TestMandateCreate:
    def test_valid_minimal(self):
        m = MandateCreate(**_valid_mandate_data())
        assert m.debtor_name == "John Doe"
        assert m.mandate_type == "recurrent"
        assert m.signature_method == "paper"
        assert m.debtor_bic is None

    def test_valid_full(self):
        m = MandateCreate(**_valid_mandate_data(
            debtor_bic="CAIXESBBXXX",
            mandate_type="one_off",
            signature_method="digital",
            notes="Test mandate",
        ))
        assert m.debtor_bic == "CAIXESBBXXX"
        assert m.mandate_type == "one_off"

    def test_invalid_iban_format(self):
        with pytest.raises(ValidationError):
            MandateCreate(**_valid_mandate_data(debtor_iban="invalid"))

    def test_iban_lowercase_rejected(self):
        with pytest.raises(ValidationError):
            MandateCreate(**_valid_mandate_data(debtor_iban="es9121000418450200051332"))

    def test_empty_debtor_name_rejected(self):
        with pytest.raises(ValidationError):
            MandateCreate(**_valid_mandate_data(debtor_name=""))

    def test_invalid_mandate_type(self):
        with pytest.raises(ValidationError):
            MandateCreate(**_valid_mandate_data(mandate_type="monthly"))

    def test_invalid_signature_method(self):
        with pytest.raises(ValidationError):
            MandateCreate(**_valid_mandate_data(signature_method="email"))

    def test_invalid_bic_format(self):
        with pytest.raises(ValidationError):
            MandateCreate(**_valid_mandate_data(debtor_bic="invalid"))

    def test_valid_bic_8_chars(self):
        m = MandateCreate(**_valid_mandate_data(debtor_bic="CAIXESBB"))
        assert m.debtor_bic == "CAIXESBB"


# --- MandateUpdate ---


class TestMandateUpdate:
    def test_all_optional(self):
        m = MandateUpdate()
        assert m.debtor_name is None
        assert m.debtor_iban is None
        assert m.notes is None

    def test_update_name(self):
        m = MandateUpdate(debtor_name="Jane Doe")
        assert m.debtor_name == "Jane Doe"

    def test_invalid_iban_on_update(self):
        with pytest.raises(ValidationError):
            MandateUpdate(debtor_iban="bad")


# --- MandateResponse ---


class TestMandateResponse:
    def test_from_attributes(self):
        data = {
            "id": 1,
            "member_id": 1,
            "mandate_reference": "MEM-00001-001",
            "creditor_id": "ES12000B12345678",
            "debtor_name": "John Doe",
            "debtor_iban": "ES9121000418450200051332",
            "debtor_bic": None,
            "mandate_type": "recurrent",
            "signature_method": "paper",
            "status": "active",
            "signed_at": date(2026, 4, 1),
            "document_path": None,
            "cancelled_at": None,
            "notes": None,
            "is_active": True,
        }
        r = MandateResponse(**data)
        assert r.mandate_reference == "MEM-00001-001"
        assert r.status == "active"


# --- RemittanceCreate ---


class TestRemittanceCreate:
    def test_valid(self):
        r = RemittanceCreate(**_valid_remittance_create())
        assert len(r.receipt_ids) == 3
        assert r.notes is None

    def test_empty_receipt_ids_rejected(self):
        with pytest.raises(ValidationError):
            RemittanceCreate(**_valid_remittance_create(receipt_ids=[]))

    def test_with_notes(self):
        r = RemittanceCreate(**_valid_remittance_create(notes="Monthly batch"))
        assert r.notes == "Monthly batch"


# --- RemittanceResponse ---


class TestRemittanceResponse:
    def test_from_attributes(self):
        data = {
            "id": 1,
            "remittance_number": "REM-2026-0001",
            "remittance_type": "sepa",
            "status": "draft",
            "emission_date": date(2026, 4, 8),
            "due_date": date(2026, 5, 1),
            "total_amount": Decimal("150.00"),
            "receipt_count": 3,
            "sepa_file_path": None,
            "creditor_name": "Club Test",
            "creditor_iban": "ES9121000418450200051332",
            "creditor_bic": "CAIXESBBXXX",
            "creditor_id": "ES12000B12345678",
            "notes": None,
            "created_by": 1,
            "is_active": True,
        }
        r = RemittanceResponse(**data)
        assert r.remittance_number == "REM-2026-0001"
        assert r.total_amount == Decimal("150.00")


class TestRemittanceDetailResponse:
    def test_with_empty_receipts(self):
        data = {
            "id": 1,
            "remittance_number": "REM-2026-0001",
            "remittance_type": "sepa",
            "status": "draft",
            "emission_date": date(2026, 4, 8),
            "due_date": date(2026, 5, 1),
            "total_amount": Decimal("0"),
            "receipt_count": 0,
            "sepa_file_path": None,
            "creditor_name": "Club",
            "creditor_iban": "ES9121000418450200051332",
            "creditor_bic": None,
            "creditor_id": "ES12000B12345678",
            "notes": None,
            "created_by": None,
            "is_active": True,
            "receipts": [],
        }
        r = RemittanceDetailResponse(**data)
        assert r.receipts == []


# --- PaymentProviderCreate ---


class TestPaymentProviderCreate:
    def test_valid_minimal(self):
        p = PaymentProviderCreate(**_valid_provider_data())
        assert p.status == "disabled"
        assert p.is_default is False
        assert p.config == {}

    def test_with_config(self):
        p = PaymentProviderCreate(**_valid_provider_data(
            config={"api_key": "sk_test_123"},
            status="test",
            is_default=True,
        ))
        assert p.config["api_key"] == "sk_test_123"
        assert p.status == "test"

    def test_invalid_status(self):
        with pytest.raises(ValidationError):
            PaymentProviderCreate(**_valid_provider_data(status="production"))

    def test_empty_provider_type_rejected(self):
        with pytest.raises(ValidationError):
            PaymentProviderCreate(provider_type="", display_name="Test")


# --- PaymentProviderUpdate ---


class TestPaymentProviderUpdate:
    def test_all_optional(self):
        p = PaymentProviderUpdate()
        assert p.display_name is None
        assert p.status is None

    def test_update_status(self):
        p = PaymentProviderUpdate(status="active")
        assert p.status == "active"


# --- PaymentProviderResponse ---


class TestPaymentProviderResponse:
    def test_from_attributes(self):
        data = {
            "id": 1,
            "provider_type": "sepa_direct_debit",
            "display_name": "SEPA",
            "status": "active",
            "config": {},
            "is_default": True,
        }
        r = PaymentProviderResponse(**data)
        assert r.provider_type == "sepa_direct_debit"
        assert r.is_default is True


# --- Org Settings with new SEPA fields ---


class TestOrgSettingsSepaFields:
    def test_response_includes_sepa_fields(self):
        data = {
            "id": 1,
            "name": "Club Test",
            "locale": "es",
            "timezone": "Europe/Madrid",
            "currency": "EUR",
            "date_format": "DD/MM/YYYY",
            "creditor_id": "ES12000B12345678",
            "sepa_format": "pain.008",
            "created_at": datetime(2026, 1, 1),
            "updated_at": datetime(2026, 1, 1),
        }
        r = OrganizationSettingsResponse(**data)
        assert r.creditor_id == "ES12000B12345678"
        assert r.sepa_format == "pain.008"

    def test_update_creditor_id(self):
        u = OrganizationSettingsUpdate(creditor_id="ES12000B12345678")
        assert u.creditor_id == "ES12000B12345678"

    def test_update_sepa_format_valid(self):
        u = OrganizationSettingsUpdate(sepa_format="pain.008")
        assert u.sepa_format == "pain.008"

    def test_update_sepa_format_invalid(self):
        with pytest.raises(ValidationError):
            OrganizationSettingsUpdate(sepa_format="n19")

    def test_update_currency_krw(self):
        u = OrganizationSettingsUpdate(currency="KRW")
        assert u.currency == "KRW"

    def test_update_currency_invalid(self):
        with pytest.raises(ValidationError):
            OrganizationSettingsUpdate(currency="euro")
