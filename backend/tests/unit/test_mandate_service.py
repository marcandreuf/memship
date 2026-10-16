"""Unit tests for mandate service — IBAN validation and reference format."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.domains.billing.mandate_service import validate_iban_format
from app.domains.billing.schemas import (
    MandateCreate,
    MandateUpdate,
    normalize_pasted_iban,
)


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

    def test_broken_check_digits_rejected(self):
        """One digit of a real IBAN changed. Structurally perfect, arithmetically wrong.

        This is the typo the pain.008 schema cannot catch either — its IBAN type
        is a bare pattern — so without this check the bank is the first thing
        that notices, and it can return the whole batch.
        """
        assert validate_iban_format("ES9121000418450200051333") is False

    def test_well_formed_nonsense_rejected(self):
        assert validate_iban_format("ZZ00NOTANIBAN123") is False


class TestPastedIbanNormalisation:
    """What a human pastes is normalised before it reaches the validator."""

    def test_grouping_spaces_are_stripped(self):
        assert (
            normalize_pasted_iban("ES91 2100 0418 4502 0005 1332")
            == "ES9121000418450200051332"
        )

    def test_lowercase_is_upper_cased(self):
        assert (
            normalize_pasted_iban("es9121000418450200051332")
            == "ES9121000418450200051332"
        )

    def test_a_pasted_iban_passes_validation_once_normalised(self):
        assert validate_iban_format(normalize_pasted_iban("ES91 2100 0418 4502 0005 1332")) is True

    def test_a_mandate_accepts_a_pasted_iban(self):
        mandate = MandateCreate(
            member_id=1,
            debtor_name="Carlos Blanch",
            debtor_iban="es91 2100 0418 4502 0005 1332",
            signed_at=date(2026, 1, 1),
        )
        assert mandate.debtor_iban == "ES9121000418450200051332"

    def test_a_mandate_still_refuses_a_bad_checksum(self):
        with pytest.raises(ValidationError):
            MandateCreate(
                member_id=1,
                debtor_name="Carlos Blanch",
                debtor_iban="ZZ00 NOTANIBAN 123",
                signed_at=date(2026, 1, 1),
            )


class TestIbanErrorCodes:
    """The 422 a rejected IBAN produces has to be translatable.

    A bare `ValueError` in a field validator reaches the administrator as
    `Value error, Invalid IBAN`, and a failed `pattern=` as the regex itself —
    English, on a screen that may be running in Catalan (#377). These assert on
    the `type` the locale files key on, not on the English message.
    """

    def _error(self, iban: str) -> dict:
        with pytest.raises(ValidationError) as exc:
            MandateCreate(
                member_id=1,
                debtor_name="Test Debtor",
                debtor_iban=iban,
                signed_at=date(2026, 10, 16),
            )
        errors = [e for e in exc.value.errors() if e["loc"] == ("debtor_iban",)]
        assert len(errors) == 1, exc.value.errors()
        return errors[0]

    def test_bad_check_digits_carry_the_invalid_iban_code(self):
        # Structurally a Spanish IBAN; last digit changed so mod-97 fails.
        assert self._error("ES9121000418450200051333")["type"] == "invalid_iban"

    def test_not_shaped_like_an_iban_carries_the_malformed_code(self):
        assert self._error("NOT-AN-IBAN-AT-ALL")["type"] == "malformed_iban"

    def test_lowercase_is_normalised_rather_than_refused(self):
        m = MandateCreate(
            member_id=1,
            debtor_name="Test Debtor",
            debtor_iban="es91 2100 0418 4502 0005 1332",
            signed_at=date(2026, 10, 16),
        )
        assert m.debtor_iban == "ES9121000418450200051332"

    def test_no_message_reaches_the_screen_with_a_pydantic_prefix(self):
        # `Value error, ` is what a bare ValueError adds. Nothing user-facing
        # should carry it, and no message should be a regular expression.
        for iban in ("ES9121000418450200051333", "NOT-AN-IBAN-AT-ALL"):
            msg = self._error(iban)["msg"]
            assert "Value error" not in msg
            assert "[A-Z]" not in msg

    def test_update_schema_refuses_the_same_way(self):
        with pytest.raises(ValidationError) as exc:
            MandateUpdate(debtor_iban="ES9121000418450200051333")
        assert exc.value.errors()[0]["type"] == "invalid_iban"
