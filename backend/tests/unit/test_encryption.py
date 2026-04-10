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
    validate_provider_config,
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

    def test_decrypt_config_handles_invalid_token(self):
        config = {"secret_key": "not-a-valid-fernet-token"}
        sensitive = ["secret_key"]
        result = decrypt_config(config, sensitive)
        # Should leave invalid value as-is
        assert result["secret_key"] == "not-a-valid-fernet-token"

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
                "mode": "webhook",
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
        assert "mode" in required
        assert "webhook_secret" not in required  # optional

    def test_get_required_fields_unknown(self):
        assert get_required_fields("unknown_type") == []


# --- Config Validation ---


class TestConfigValidation:
    def test_valid_stripe_config(self):
        config = {
            "secret_key": "sk_live_abc123",
            "publishable_key": "pk_live_xyz456",
            "mode": "webhook",
        }
        errors = validate_provider_config("stripe", config)
        assert errors == []

    def test_stripe_missing_required(self):
        config = {"secret_key": "sk_live_abc", "mode": "webhook"}
        errors = validate_provider_config("stripe", config)
        assert any("Publishable Key" in e for e in errors)

    def test_stripe_invalid_key_prefix(self):
        config = {
            "secret_key": "invalid_key",
            "publishable_key": "pk_live_xyz",
            "mode": "webhook",
        }
        errors = validate_provider_config("stripe", config)
        assert any("sk_" in e for e in errors)

    def test_stripe_invalid_select_value(self):
        config = {
            "secret_key": "sk_live_abc",
            "publishable_key": "pk_live_xyz",
            "mode": "invalid_mode",
        }
        errors = validate_provider_config("stripe", config)
        assert any("must be one of" in e for e in errors)

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
        assert any("numeric" in e.lower() for e in errors)

    def test_redsys_invalid_currency_code(self):
        config = {
            "merchant_code": "123456789",
            "terminal_id": "001",
            "secret_key": "secret123",
            "environment": "test",
            "currency_code": "EU",
        }
        errors = validate_provider_config("redsys", config)
        assert any("3-digit" in e for e in errors)

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
        assert any("Unknown" in e for e in errors)
