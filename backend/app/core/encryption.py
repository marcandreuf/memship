"""Fernet-based encryption for payment provider credentials.

Sensitive fields (API keys, secrets) are encrypted before DB storage
and decrypted on read. Masked versions are used in API responses.
"""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet

from app.core.config import settings

logger = logging.getLogger(__name__)


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


# Every Fernet token is base64url of a structure whose first byte is 0x80, so
# it always begins with this. It is how a value that *was* encrypted and can no
# longer be read is told apart from one that was never encrypted at all.
_FERNET_PREFIX = "gAAAAA"


def decrypt_config(config: dict, sensitive_fields: list[str]) -> dict:
    """Decrypt sensitive fields in a provider config dict.

    A field that was encrypted and can no longer be decrypted is **dropped**,
    not passed through. The previous behaviour left the ciphertext in place, so
    every caller received a Fernet token and used it as the credential — and
    for a Stripe signing secret that is the quietest failure memship has: each
    webhook fails verification and is discarded, the member is shown success,
    and the receipt stays unpaid (#354).

    Dropping rather than raising keeps the provider repairable from the UI. A
    missing required field is a case the product already handles: the settings
    screen renders it unset, ``_require_ready`` answers ``provider_not_ready``,
    and the value can be re-entered. Raising would take the settings screen
    down and leave no way to fix it there — which is exactly the state a key
    rotation would create.

    A value that does **not** look like a Fernet token is left alone. It was
    never encrypted, so it is its own plaintext and returning it is correct;
    dropping it would break a provider that works. That distinction is the
    difference between fixing a silent failure and causing an outage on an
    instance whose config predates encryption or was written directly.
    """
    result = dict(config)
    for field in sensitive_fields:
        if field in result and result[field]:
            try:
                result[field] = decrypt_value(result[field])
            except Exception:
                value = result[field]
                if isinstance(value, str) and value.startswith(_FERNET_PREFIX):
                    logger.warning(
                        "Could not decrypt %r — dropping it. The stored value "
                        "is ciphertext the current key does not open (rotated "
                        "or changed SECRET_KEY); it must be re-entered.",
                        field,
                    )
                    del result[field]
                else:
                    logger.info(
                        "%r is not encrypted; using it as stored.", field
                    )
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
