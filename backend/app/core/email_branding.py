"""Branding for outgoing email, resolved from ``organization_settings``.

Every email is wrapped in a shared layout (``templates/email/_base.html``) whose
header, footer and accent colour come from the single organisation row. The
resolver mirrors ``email._resolve_transport``: it opens its own short-lived
session (callers — Celery tasks, request handlers, the billing service — do not
all carry one) and **never raises**. A DB hiccup degrades an email to default
branding; it must not turn a password reset into a 500.

Branding changes about never, while an announcement broadcast renders once per
recipient, so the resolved value is cached for ``_CACHE_TTL_SECONDS``. A logo or
colour change therefore reaches the next email within five minutes.
"""

import logging
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_NAME = "Memship"
DEFAULT_COLOR = "#0083ad"
ON_DARK = "#ffffff"
ON_LIGHT = "#1f2328"

_CACHE_TTL_SECONDS = 300

# A logo URL built on one of these resolves only inside the deployment, so it
# would render as a broken image in the recipient's client. Better no logo.
_NON_PUBLIC_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1", ""})


@dataclass(frozen=True)
class EmailBranding:
    """Everything the email layout needs about the sending organisation."""

    name: str = DEFAULT_NAME
    logo_url: str | None = None
    color: str = DEFAULT_COLOR
    on_color: str = ON_DARK
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    website_label: str | None = None


_cache: tuple[float, EmailBranding] | None = None


def reset_branding_cache() -> None:
    """Drop the cached branding — used by tests, and safe to call anywhere."""
    global _cache
    _cache = None


# --- colour helpers ---

def _parse_hex(value: str | None) -> tuple[int, int, int] | None:
    """Parse ``#rgb`` / ``#rrggbb`` into 0-255 components, or None if unusable."""
    if not value:
        return None
    v = value.strip().lstrip("#")
    if len(v) == 3:
        v = "".join(ch * 2 for ch in v)
    if len(v) != 6:
        return None
    try:
        return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
    except ValueError:
        return None


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    """WCAG relative luminance of an sRGB colour."""
    def channel(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a: float, b: float) -> float:
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def readable_on(color: str) -> str:
    """Pick the header text colour with the better contrast against ``color``.

    ``brand_color`` is superadmin-set and may be pale; white-on-yellow would be
    unreadable, so the choice is computed rather than assumed.
    """
    rgb = _parse_hex(color)
    if rgb is None:
        return ON_DARK
    bg = _relative_luminance(rgb)
    on_dark = _contrast(bg, _relative_luminance(_parse_hex(ON_DARK)))
    on_light = _contrast(bg, _relative_luminance(_parse_hex(ON_LIGHT)))
    return ON_DARK if on_dark >= on_light else ON_LIGHT


def normalize_color(value: str | None) -> str:
    """Return a usable hex colour, falling back to the product default."""
    rgb = _parse_hex(value)
    if rgb is None:
        return DEFAULT_COLOR
    return "#{:02x}{:02x}{:02x}".format(*rgb)


# --- URL helpers ---

def absolute_logo_url(stored: str | None) -> str | None:
    """Turn a stored ``/uploads/org/<file>`` path into a URL a mail client can fetch.

    ``org`` is the one public prefix in ``app/api/uploads.py``, so no session is
    involved. Returns None when the logo is unset, or when the public backend URL
    is still a localhost default — a link the recipient could never resolve.
    """
    if not stored:
        return None
    if stored.startswith(("http://", "https://")):
        return stored
    base = (settings.BACKEND_PUBLIC_URL or "").strip().rstrip("/")
    if not base:
        return None
    host = (urlsplit(base).hostname or "").lower()
    if host in _NON_PUBLIC_HOSTS:
        return None
    return f"{base}/{stored.lstrip('/')}"


def normalize_website(value: str | None) -> tuple[str | None, str | None]:
    """Return ``(href, label)`` for the footer website link.

    A club typing ``example.org`` into settings must still produce a working
    link, so a missing scheme is filled in; the label drops the scheme and any
    trailing slash because that is what reads as a website in a footer.
    """
    if not value:
        return None, None
    raw = value.strip()
    if not raw:
        return None, None
    href = raw if raw.startswith(("http://", "https://")) else f"https://{raw}"
    label = href.split("://", 1)[1].rstrip("/")
    return href, label


# --- resolution ---

def _load_branding() -> EmailBranding:
    from app.db import session as db_session
    from app.domains.organizations.models import OrganizationSettings

    db = db_session.SessionLocal()
    try:
        org = (
            db.query(OrganizationSettings)
            .filter(OrganizationSettings.id == 1)
            .first()
        )
        if org is None:
            return EmailBranding()
        color = normalize_color(org.brand_color)
        href, label = normalize_website(org.website)
        return EmailBranding(
            name=(org.name or "").strip() or DEFAULT_NAME,
            logo_url=absolute_logo_url(org.logo_url),
            color=color,
            on_color=readable_on(color),
            email=(org.email or None),
            phone=(org.phone or None),
            website=href,
            website_label=label,
        )
    finally:
        db.close()


def get_email_branding() -> EmailBranding:
    """Resolve branding for the email layout, cached and failure-tolerant."""
    global _cache
    now = time.monotonic()
    if _cache is not None and now - _cache[0] < _CACHE_TTL_SECONDS:
        return _cache[1]
    try:
        branding = _load_branding()
    except Exception as e:  # noqa: BLE001 — branding must never break a send
        logger.warning(f"Email branding resolution failed, using defaults: {e}")
        return EmailBranding()
    _cache = (now, branding)
    return branding