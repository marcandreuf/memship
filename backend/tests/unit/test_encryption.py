"""Unit tests for encryption utility and provider config validation."""

import pytest

from app.core.encryption import (
    decrypt_config,
    decrypt_value,
    encrypt_config,
    encrypt_value,
    mask_config,
    mask_value,
)
from app.domains.billing.provider_config import (
    PROVIDER_CONFIG_SCHEMAS,
    get_required_fields,
    get_sensitive_fields,
    is_checkbox_true,
    member_payment_methods,
    validate_provider_config,
    validate_provider_format,
)


# --- Encryption / Decryption ---


class TestEncryptDecrypt:
    def test_encrypt_and_decrypt_value(self):
        original = "sk_live_abc123xyz"
        encrypted = encrypt_value(original)
        assert encrypted != original
        assert decrypt_value(encrypted) == original

    def test_encrypt_value_produces_different_tokens(self):
        """Fernet includes timestamp, so each call produces a different token."""
        v1 = encrypt_value("same_value")
        v2 = encrypt_value("same_value")
        assert v1 != v2  # different ciphertext, same plaintext

    def test_encrypt_config_only_encrypts_sensitive(self):
        config = {"secret_key": "sk_live_abc", "publishable_key": "pk_live_xyz"}
        sensitive = ["secret_key"]
        result = encrypt_config(config, sensitive)
        assert result["secret_key"] != "sk_live_abc"
        assert result["publishable_key"] == "pk_live_xyz"

    def test_encrypt_config_skips_empty_values(self):
        config = {"secret_key": "", "publishable_key": "pk_live_xyz"}
        sensitive = ["secret_key"]
        result = encrypt_config(config, sensitive)
        assert result["secret_key"] == ""

    def test_decrypt_config_restores_values(self):
        config = {"secret_key": "sk_live_abc", "mode": "webhook"}
        sensitive = ["secret_key"]
        encrypted = encrypt_config(config, sensitive)
        decrypted = decrypt_config(encrypted, sensitive)
        assert decrypted["secret_key"] == "sk_live_abc"
        assert decrypted["mode"] == "webhook"

    def test_a_field_encrypted_under_another_key_is_dropped(self):
        """The ciphertext must never reach a caller as if it were the secret.

        This is #354. A rotated or changed SECRET_KEY is the real trigger. The
        old behaviour left the token in place, so a caller used a Fernet blob as
        the credential — and for a Stripe signing secret that means every
        webhook fails verification and is discarded while the member is shown
        success. Dropping it puts the provider into the missing-required-field
        state the product already handles, so the value can be re-entered.
        """
        from cryptography.fernet import Fernet

        other_key = Fernet(Fernet.generate_key())
        token = other_key.encrypt(b"sk_live_abc").decode()
        config = {"secret_key": token, "mode": "webhook"}

        result = decrypt_config(config, ["secret_key"])

        assert "secret_key" not in result
        assert token not in result.values()
        # Non-sensitive fields are untouched.
        assert result["mode"] == "webhook"

    def test_a_value_that_was_never_encrypted_is_left_alone(self):
        """Not every undecryptable value is ciphertext.

        A value that does not look like a Fernet token was never encrypted, so
        it is its own plaintext and returning it is correct. Dropping it would
        break a provider that works — on an instance whose config predates
        encryption, or was written directly — which would turn the #354 fix
        into an outage. Every Fernet token starts "gAAAAA"; this does not.
        """
        config = {"secret_key": "sk_live_plain", "mode": "webhook"}

        result = decrypt_config(config, ["secret_key"])

        assert result["secret_key"] == "sk_live_plain"
        assert result["mode"] == "webhook"

    def test_encrypt_config_no_sensitive_fields(self):
        config = {"format": "pain.008.001.02"}
        result = encrypt_config(config, [])
        assert result == config

    def test_roundtrip_all_provider_types(self):
        """Encrypt → decrypt roundtrip for every provider type's sensitive fields."""
        test_configs = {
            "sepa_direct_debit": {"format": "pain.008.001.02"},
            "stripe": {
                "secret_key": "sk_live_test123",
                "publishable_key": "pk_live_test456",
                "webhook_secret": "whsec_test789",
            },
            "redsys": {
                "merchant_code": "123456789",
                "terminal_id": "001",
                "secret_key": "redsys_secret",
                "environment": "test",
                "currency_code": "978",
            },
            "goCardless": {
                "access_token": "gc_token_abc",
                "webhook_secret": "gc_whsec_xyz",
                "environment": "sandbox",
            },
            "paypal": {
                "client_id": "pp_client_abc",
                "client_secret": "pp_secret_xyz",
                "environment": "sandbox",
            },
        }
        for ptype, config in test_configs.items():
            sensitive = get_sensitive_fields(ptype)
            encrypted = encrypt_config(config, sensitive)
            decrypted = decrypt_config(encrypted, sensitive)
            assert decrypted == config, f"Roundtrip failed for {ptype}"


# --- Masking ---


class TestMasking:
    def test_mask_value_long(self):
        assert mask_value("sk_live_abc123xyz") == "****3xyz"

    def test_mask_value_short(self):
        assert mask_value("abc") == "****"

    def test_mask_value_empty(self):
        assert mask_value("") == "****"

    def test_mask_config(self):
        config = {
            "secret_key": "sk_live_abc123xyz",
            "publishable_key": "pk_live_456",
            "mode": "webhook",
        }
        result = mask_config(config, ["secret_key"])
        assert result["secret_key"] == "****3xyz"
        assert result["publishable_key"] == "pk_live_456"  # not sensitive
        assert result["mode"] == "webhook"

    def test_mask_config_empty_sensitive_value(self):
        config = {"secret_key": "", "mode": "webhook"}
        result = mask_config(config, ["secret_key"])
        assert result["secret_key"] == ""  # empty stays empty


# --- Provider Config Schemas ---


class TestProviderConfig:
    def test_all_five_types_defined(self):
        expected = {"sepa_direct_debit", "stripe", "redsys", "goCardless", "paypal"}
        assert set(PROVIDER_CONFIG_SCHEMAS.keys()) == expected

    def test_get_sensitive_fields_stripe(self):
        assert get_sensitive_fields("stripe") == ["secret_key", "webhook_secret"]

    def test_get_sensitive_fields_sepa(self):
        assert get_sensitive_fields("sepa_direct_debit") == []

    def test_get_sensitive_fields_unknown(self):
        assert get_sensitive_fields("unknown_type") == []

    def test_get_required_fields_stripe(self):
        required = get_required_fields("stripe")
        assert "secret_key" in required
        assert "publishable_key" in required
        assert "webhook_secret" in required

    def test_get_required_fields_unknown(self):
        assert get_required_fields("unknown_type") == []


class TestMemberPaymentMethods:
    """`/active-methods` tells the portal which pay buttons to draw, and Bizum is
    the one that depends on something memship cannot see — whether the club's bank
    enabled it on the terminal (#405)."""

    REDSYS = {
        "merchant_code": "123456789",
        "terminal_id": "001",
        "secret_key": "secret123",
        "environment": "test",
        "currency_code": "978",
    }

    def test_redsys_offers_card_but_not_bizum_by_default(self):
        """The default matters more than the toggle: a config saved before this
        existed has no key, and must not keep offering a button that fails."""
        assert member_payment_methods("redsys", self.REDSYS) == ["card"]

    def test_redsys_offers_bizum_once_it_is_switched_on(self):
        config = {**self.REDSYS, "enable_bizum": "true"}
        assert member_payment_methods("redsys", config) == ["card", "bizum"]

    def test_switching_bizum_off_leaves_card_alone(self):
        config = {**self.REDSYS, "enable_bizum": "false"}
        assert member_payment_methods("redsys", config) == ["card"]

    def test_a_real_boolean_works_as_well_as_the_form_string(self):
        """The settings form stores strings; the API accepts either."""
        assert "bizum" in member_payment_methods(
            "redsys", {**self.REDSYS, "enable_bizum": True}
        )

    def test_the_other_providers_report_their_own_method(self):
        assert member_payment_methods("stripe", {}) == ["card"]
        assert member_payment_methods("sepa_direct_debit", {}) == ["direct_debit"]

    def test_a_provider_that_cannot_be_active_offers_nothing(self):
        assert member_payment_methods("paypal", {}) == []
        assert member_payment_methods("unknown", {}) == []

    def test_a_missing_config_is_not_an_error(self):
        """The column is nullable, and a row with no config at all is still a row."""
        assert member_payment_methods("redsys", None) == ["card"]

    @pytest.mark.parametrize("value", ["true", "True", " TRUE ", "1", "yes", "on", True])
    def test_truthy_checkbox_values(self, value):
        assert is_checkbox_true(value) is True

    @pytest.mark.parametrize("value", ["false", "", "0", "no", "off", None, False, 0, []])
    def test_everything_else_is_off(self, value):
        assert is_checkbox_true(value) is False


# --- Config Validation ---


class TestConfigValidation:
    def test_valid_stripe_config(self):
        config = {
            "secret_key": "sk_live_abc123",
            "publishable_key": "pk_live_xyz456",
            "webhook_secret": "whsec_test789",
        }
        errors = validate_provider_config("stripe", config)
        assert errors == []

    def test_stripe_missing_required(self):
        config = {"secret_key": "sk_live_abc", "webhook_secret": "whsec_test"}
        errors = validate_provider_config("stripe", config)
        assert {"code": "missing_required_field", "field": "publishable_key"} in errors

    def test_stripe_missing_webhook_secret(self):
        config = {
            "secret_key": "sk_live_abc",
            "publishable_key": "pk_live_xyz",
        }
        errors = validate_provider_config("stripe", config)
        assert {"code": "missing_required_field", "field": "webhook_secret"} in errors

    def test_stripe_invalid_key_prefix(self):
        config = {
            "secret_key": "invalid_key",
            "publishable_key": "pk_live_xyz",
            "webhook_secret": "whsec_test",
        }
        errors = validate_provider_config("stripe", config)
        assert {"code": "must_start_with", "field": "secret_key", "prefix": "sk_"} in errors

    def test_stripe_webhook_secret_prefix(self):
        """A signing secret memship cannot verify, in the one way it can.

        Only Stripe knows whether the value is correct, and a wrong one fails
        silently at the webhook — every confirmation discarded, the member shown
        success, the receipt left unpaid. The prefix catches the paste that took
        the wrong field off the dashboard.
        """
        config = {
            "secret_key": "sk_live_xyz",
            "publishable_key": "pk_live_xyz",
            "webhook_secret": "nonsense",
        }
        errors = validate_provider_config("stripe", config)
        assert {
            "code": "must_start_with",
            "field": "webhook_secret",
            "prefix": "whsec_",
        } in errors

    def test_valid_redsys_config(self):
        config = {
            "merchant_code": "123456789",
            "terminal_id": "001",
            "secret_key": "secret123",
            "environment": "test",
            "currency_code": "978",
        }
        errors = validate_provider_config("redsys", config)
        assert errors == []

    def test_redsys_non_numeric_merchant(self):
        config = {
            "merchant_code": "abc",
            "terminal_id": "001",
            "secret_key": "secret123",
            "environment": "test",
            "currency_code": "978",
        }
        errors = validate_provider_config("redsys", config)
        assert {"code": "must_be_numeric", "field": "merchant_code"} in errors

    def test_redsys_invalid_currency_code(self):
        config = {
            "merchant_code": "123456789",
            "terminal_id": "001",
            "secret_key": "secret123",
            "environment": "test",
            "currency_code": "EU",
        }
        errors = validate_provider_config("redsys", config)
        assert {"code": "must_be_digits", "field": "currency_code", "length": 3} in errors

    def test_valid_sepa_config(self):
        config = {"format": "pain.008.001.02"}
        errors = validate_provider_config("sepa_direct_debit", config)
        assert errors == []

    def test_valid_gocardless_config(self):
        config = {
            "access_token": "gc_token_abc",
            "environment": "sandbox",
        }
        errors = validate_provider_config("goCardless", config)
        assert errors == []

    def test_valid_paypal_config(self):
        config = {
            "client_id": "pp_client",
            "client_secret": "pp_secret",
            "environment": "sandbox",
        }
        errors = validate_provider_config("paypal", config)
        assert errors == []

    def test_unknown_provider_type(self):
        errors = validate_provider_config("unknown", {})
        assert errors == [{"code": "unknown_provider_type", "provider_type": "unknown"}]


class TestAPrefixAloneIsNotAKey:
    """A paste that grabbed only the first characters of a Stripe key keeps the
    prefix, so the prefix rule accepted it and stored it; it then failed at
    Stripe when a member tried to pay. Caught here as far as it honestly can
    be — the length of a real key is Stripe's business, not memship's."""

    @pytest.mark.parametrize(
        "field,prefix",
        [
            ("secret_key", "sk_"),
            ("publishable_key", "pk_"),
            ("webhook_secret", "whsec_"),
        ],
    )
    def test_the_bare_prefix_is_refused(self, field, prefix):
        errors = validate_provider_format("stripe", {field: prefix})
        assert {"code": "prefix_only", "field": field, "prefix": prefix} in errors

    def test_one_character_past_the_prefix_is_accepted(self):
        """Not a length rule: anything beyond the prefix is Stripe's to judge."""
        assert validate_provider_format("stripe", {"secret_key": "sk_x"}) == []

    def test_a_wrong_prefix_still_reports_the_prefix_rule(self):
        """The two codes must not both fire — the screen would say the value is
        the prefix and does not start with it."""
        errors = validate_provider_format("stripe", {"secret_key": "pk_live_abc"})
        assert errors == [
            {"code": "must_start_with", "field": "secret_key", "prefix": "sk_"}
        ]


class TestOptionMembershipIsAFormatRule:
    """A select's value is either one of its options or nonsense, whatever the
    provider's status — so it is checked by the format pass, which runs on every
    save, not only by the readiness pass that runs at activation (#406)."""

    def test_format_alone_rejects_an_unknown_option(self):
        errors = validate_provider_format("redsys", {"environment": "staging"})
        assert errors == [
            {
                "code": "invalid_option",
                "field": "environment",
                "options": ["test", "production"],
            }
        ]

    def test_format_alone_accepts_a_known_option(self):
        assert validate_provider_format("redsys", {"environment": "production"}) == []

    def test_format_alone_stays_silent_about_a_missing_option(self):
        """Missing is the readiness pass's business: a half-filled config is a
        normal thing to save while the provider is switched off."""
        assert validate_provider_format("redsys", {}) == []

    def test_readiness_still_reports_an_unknown_option(self):
        errors = validate_provider_config(
            "sepa_direct_debit", {"format": "pain.001.001.03"}
        )
        assert {
            "code": "invalid_option",
            "field": "format",
            "options": ["pain.008.001.02"],
        } in errors

    def test_a_missing_required_select_reports_once(self):
        """Presence and membership must not both fire for the same empty field:
        the screen would say it is required and not one of the options."""
        errors = validate_provider_config("sepa_direct_debit", {"format": ""})
        assert errors == [{"code": "missing_required_field", "field": "format"}]


class TestValidationErrorsAreTranslatable:
    """Messages reach an administrator's screen and the organization may not be
    running in English, so validation emits codes rather than sentences (#223)."""

    def test_no_error_carries_a_rendered_sentence(self):
        """Every error is a code plus parameters — a field key, never a label."""
        cases = [
            ("stripe", {}),
            ("stripe", {"secret_key": "nope", "publishable_key": "pk_x", "webhook_secret": "w"}),
            ("redsys", {"merchant_code": "abc", "terminal_id": "x", "secret_key": "s",
                        "environment": "test", "currency_code": "EU"}),
            ("sepa_direct_debit", {"format": "not-a-format"}),
            ("unknown", {}),
        ]
        for provider_type, config in cases:
            for error in validate_provider_config(provider_type, config):
                assert isinstance(error, dict), (provider_type, error)
                assert "code" in error, (provider_type, error)
                # A label would be untranslatable; the key is what the locale
                # files are indexed by.
                assert "label" not in error and "message" not in error, error
                if "field" in error:
                    assert error["field"] == error["field"].lower()

    def test_an_invalid_option_reports_what_was_allowed(self):
        errors = validate_provider_config("sepa_direct_debit", {"format": "wrong"})
        assert errors == [
            {
                "code": "invalid_option",
                "field": "format",
                "options": ["pain.008.001.02"],
            }
        ]

    def test_every_emitted_code_has_a_field_the_ui_can_name(self):
        """A code carrying a field must name one the schema declares, or the UI
        has nothing to look up in its locale files."""
        from app.domains.billing.provider_config import PROVIDER_CONFIG_SCHEMAS

        for provider_type, schema in PROVIDER_CONFIG_SCHEMAS.items():
            keys = {f["key"] for f in schema["fields"]}
            for error in validate_provider_config(provider_type, {}):
                if "field" in error:
                    assert error["field"] in keys, (provider_type, error)
