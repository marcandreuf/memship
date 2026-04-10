"""Fernet-based encryption for payment provider credentials.

Sensitive fields (API keys, secrets) are encrypted before DB storage
and decrypted on read. Masked versions are used in API responses.
"""

import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import settings


def get_fernet() -> Fernet:
    """Create a Fernet instance from the application SECRET_KEY."""
    key = base64.urlsafe_b64encode(
        hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    )
    return key, Fernet(key)


_fernet_cache: Fernet | None = None


def _fernet() -> Fernet:
    global _fernet_cache
    if _fernet_cache is None:
        _, _fernet_cache = get_fernet()
    return _fernet_cache


def encrypt_value(value: str) -> str:
    """Encrypt a single string value. Returns a Fernet token string."""
    return _fernet().encrypt(value.encode()).decode()


def decrypt_value(value: str) -> str:
    """Decrypt a single Fernet token string."""
    return _fernet().decrypt(value.encode()).decode()


def encrypt_config(config: dict, sensitive_fields: list[str]) -> dict:
    """Encrypt sensitive fields in a provider config dict.

    Non-sensitive fields and empty strings are left as-is.
    """
    result = dict(config)
    for field in sensitive_fields:
        if field in result and result[field]:
            result[field] = encrypt_value(result[field])
    return result


def decrypt_config(config: dict, sensitive_fields: list[str]) -> dict:
    """Decrypt sensitive fields in a provider config dict."""
    result = dict(config)
    for field in sensitive_fields:
        if field in result and result[field]:
            try:
                result[field] = decrypt_value(result[field])
            except Exception:
                # If decryption fails (e.g. key rotation), leave as-is
                pass
    return result


def mask_value(value: str) -> str:
    """Mask a sensitive value, showing only the last 4 characters."""
    if not value or len(value) <= 4:
        return "****"
    return "****" + value[-4:]


def mask_config(config: dict, sensitive_fields: list[str]) -> dict:
    """Mask sensitive fields in a provider config dict for API responses."""
    result = dict(config)
    for field in sensitive_fields:
        if field in result and result[field]:
            result[field] = mask_value(result[field])
    return result
