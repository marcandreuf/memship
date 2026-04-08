"""Unit tests for mandate service — IBAN validation and reference format."""

import pytest

from app.domains.billing.mandate_service import validate_iban_format


class TestIbanValidation:
    def test_valid_spanish_iban(self):
        assert validate_iban_format("ES9121000418450200051332") is True

    def test_valid_german_iban(self):
        assert validate_iban_format("DE89370400440532013000") is True

    def test_valid_french_iban(self):
        assert validate_iban_format("FR7630006000011234567890189") is True

    def test_valid_uk_iban(self):
        assert validate_iban_format("GB29NWBK60161331926819") is True

    def test_lowercase_rejected(self):
        assert validate_iban_format("es9121000418450200051332") is False

    def test_too_short(self):
        assert validate_iban_format("ES91") is False

    def test_missing_country_code(self):
        assert validate_iban_format("9121000418450200051332") is False

    def test_empty_string(self):
        assert validate_iban_format("") is False

    def test_spaces_rejected(self):
        assert validate_iban_format("ES91 2100 0418 4502 0005 1332") is False

    def test_special_chars_rejected(self):
        assert validate_iban_format("ES91-2100-0418") is False
