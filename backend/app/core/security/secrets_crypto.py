"""Symmetric encryption for provider secrets stored in the database.

SSO credentials entered through the settings screen (a Google client secret, an
Apple ``.p8`` key) are stored Fernet-encrypted so a database dump on its own
leaks nothing — the key never lives in the database.

Key resolution:

1. ``MEMSHIP_SECRET_KEY`` env var, when set, wins (supply it from a secrets
   manager for the strictest setup).
2. Otherwise a per-install key is auto-generated on first use and persisted to
   ``SECRETS_KEY_FILE`` (default ``<STORAGE_LOCAL_PATH>/secret.key``), which must
   sit on a persistent volume. This means a usable key is essentially always
   present, so the settings screen needs no manual key step.

The only time no key is available is when the key file cannot be read or written
(e.g. a read-only volume); the settings screen still refuses to store secret
fields in that case rather than downgrading them to plaintext.
"""

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class SecretsKeyMissingError(Exception):
    """No usable encryption key could be resolved (env unset and file unwritable)."""


class SecretDecryptError(Exception):
    """A stored ciphertext could not be decrypted (wrong or rotated key)."""


# Cache only the file-sourced key so we neither regenerate it nor re-read the file
# on every call. The env override is always read fresh (cheap, and lets it change).
_file_key_cache: str | None = None


def _key_file_path() -> Path:
    if settings.SECRETS_KEY_FILE:
        return Path(settings.SECRETS_KEY_FILE)
    return Path(settings.STORAGE_LOCAL_PATH) / "secret.key"


def _load_or_create_file_key() -> str | None:
    """Return the persisted key, generating and writing one on first use.

    Returns ``None`` when the key file can be neither read nor created.
    """
    global _file_key_cache
    if _file_key_cache:
        return _file_key_cache

    path = _key_file_path()
    try:
        if path.exists():
            existing = path.read_text(encoding="utf-8").strip()
            if existing:
                _file_key_cache = existing
                return existing
        # First boot with no key configured: mint one and persist it.
        key = Fernet.generate_key().decode()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(key, encoding="utf-8")
        try:
            os.chmod(path, 0o600)  # best-effort; a no-op on some platforms
        except OSError:
            pass
        _file_key_cache = key
        return key
    except OSError:
        return None


def reset_key_cache() -> None:
    """Drop the cached file key (used by tests that repoint the key file)."""
    global _file_key_cache
    _file_key_cache = None


def _resolve_key() -> str | None:
    if settings.MEMSHIP_SECRET_KEY:
        return settings.MEMSHIP_SECRET_KEY
    return _load_or_create_file_key()


def _fernet() -> Fernet:
    key = _resolve_key()
    if not key:
        raise SecretsKeyMissingError()
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:  # malformed key
        raise SecretsKeyMissingError() from exc


def secrets_available() -> bool:
    """True when a usable encryption key is available (env or key file)."""
    try:
        _fernet()
        return True
    except SecretsKeyMissingError:
        return False


def encrypt(plaintext: str) -> str:
    """Return the Fernet ciphertext for ``plaintext``.

    Raises :class:`SecretsKeyMissingError` when no key is available.
    """
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Return the plaintext for a stored ciphertext.

    Raises :class:`SecretsKeyMissingError` when no key is available, or
    :class:`SecretDecryptError` when the key cannot decrypt this value.
    """
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise SecretDecryptError() from exc