"""The shared ``Email`` field type (#191).

An address is compared as an opaque string everywhere it is used — login,
password reset, the taken-address check on signup — so one capital resolves to
no account at all. Normalising at the schema boundary is what makes those
comparisons safe, and it has to hold for *every* module that accepts an
address, which is why there is one type rather than a copy per domain.

The ordering the fix rests on is asserted directly: stripping and lower-casing
run before the pattern is matched, so a padded address normalises instead of
being rejected.
"""

import pytest
from pydantic import BaseModel, ValidationError

from app.core.schema_types import Email, normalize_email


class Model(BaseModel):
    email: Email


class TestNormalisation:
    def test_it_lower_cases(self):
        assert Model(email="Marc.Andreu@Example.com").email == "marc.andreu@example.com"

    def test_it_strips_surrounding_whitespace(self):
        assert Model(email="  marc@example.com  ").email == "marc@example.com"

    def test_it_strips_and_lower_cases_together(self):
        assert Model(email=" MARC@EXAMPLE.COM\n").email == "marc@example.com"

    def test_an_already_normal_address_is_untouched(self):
        assert Model(email="marc@example.com").email == "marc@example.com"

    def test_the_pattern_is_matched_after_normalising_not_before(self):
        """A padded address would fail the regex — `\\s` is excluded and anchored.

        If the pattern ran first this would raise, and the strip would only ever
        apply to input that did not need it.
        """
        assert Model(email="\tMarc@Example.com ").email == "marc@example.com"


class TestValidation:
    @pytest.mark.parametrize(
        "value",
        [
            "no-at-sign",
            "no@tld",
            "two@@at.com",
            "spaces in@example.com",
            "@example.com",
            "marc@",
            "",
        ],
    )
    def test_it_still_rejects_what_it_rejected_before(self, value):
        with pytest.raises(ValidationError):
            Model(email=value)

    @pytest.mark.parametrize(
        "value",
        [
            "İrem@example.com",  # İ: Python folds to i + U+0307, Postgres to i
            "josé@example.com",
            "marc@münchen.de",
            "marc@example.cöm",
        ],
    )
    def test_it_rejects_a_non_ascii_address(self, value):
        """The application and the unique index fold case with different
        rules, and they agree only on ASCII. Accepting the rest let one typed
        address be stored twice, or stored once and never matched (#242).
        """
        with pytest.raises(ValidationError):
            Model(email=value)

    def test_every_accepted_character_is_ascii(self):
        """The atom is the printable ASCII range less `@`; nothing outside it
        gets through, whatever the surrounding shape."""
        for code in range(0x80, 0x250):
            with pytest.raises(ValidationError):
                Model(email=f"a{chr(code)}b@example.com")

    def test_dev_domains_validate(self):
        """The reason this is a regex and not EmailStr."""
        assert Model(email="admin@memship.test").email == "admin@memship.test"
        assert Model(email="admin@memship.local").email == "admin@memship.local"

    def test_it_caps_the_length(self):
        with pytest.raises(ValidationError):
            Model(email="a" * 250 + "@example.com")

    @pytest.mark.parametrize("value", [None, 42, ["a@b.com"], {"email": "a@b.com"}])
    def test_a_non_string_is_a_clean_validation_error(self, value):
        """The normaliser hands it on rather than raising AttributeError."""
        with pytest.raises(ValidationError):
            Model(email=value)


class TestNormalizeEmailDirectly:
    """The paths with no request schema call this function, not the type."""

    def test_it_strips_and_lower_cases(self):
        assert normalize_email("  MARC@Example.COM ") == "marc@example.com"

    def test_it_leaves_a_non_string_untouched(self):
        assert normalize_email(None) is None
        assert normalize_email(42) == 42

    def test_it_does_not_validate(self):
        """Shape is the annotated type's job; this only normalises."""
        assert normalize_email(" NOT-AN-EMAIL ") == "not-an-email"
