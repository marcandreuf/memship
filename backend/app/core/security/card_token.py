"""Signed membership-card tokens.

Compact HMAC-signed tokens for the digital member card / QR check-in. The token
encodes the member's stable primary key (always present, unlike the nullable
member_number) plus a truncated HMAC-SHA256 signature keyed by SECRET_KEY. The
signature makes the token unforgeable; verification only authenticates identity,
so the scan endpoint looks up the member's *live* status.

Mirrors the HS256 signing pattern in ``app/core/security/jwt.py`` — no new secret
column, and shorter than a JWT for a clean, small QR code.
"""

import hashlib
import hmac

from app.core.config import settings

# 16 bytes → 32 hex chars: unforgeable in practice, keeps the QR compact.
_SIGNATURE_HEX_LEN = 32


def _signature(member_id: int) -> str:
    digest = hmac.new(
        settings.SECRET_KEY.encode(),
        str(member_id).encode(),
        hashlib.sha256,
    ).hexdigest()
    return digest[:_SIGNATURE_HEX_LEN]


def sign_card_token(member_id: int) -> str:
    """Return ``"{member_id}.{signature}"`` for the given member."""
    return f"{member_id}.{_signature(member_id)}"


def verify_card_token(token: str | None) -> int | None:
    """Return the member id if the token is valid, else ``None``.

    Constant-time signature comparison; ``None`` on any malformed or tampered
    input.
    """
    if not token or "." not in token:
        return None

    id_part, _, sig = token.partition(".")
    try:
        member_id = int(id_part)
    except ValueError:
        return None
    if member_id <= 0:
        return None

    if not hmac.compare_digest(sig, _signature(member_id)):
        return None
    return member_id
