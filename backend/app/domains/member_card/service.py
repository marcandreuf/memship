"""Member card service — build card DTO, render QR + PDF, verify scans.

No models: everything derives from existing member/person/organization data.
"""

import base64
import io
import mimetypes
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.security.card_token import sign_card_token, verify_card_token
from app.domains.members.models import Member
from app.domains.organizations.models import OrganizationSettings

TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "pdf"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=True,
)


class InvalidCardToken(Exception):
    """The scanned token is malformed or its signature does not match."""


class CardMemberNotFound(Exception):
    """The token is valid but the referenced member no longer exists."""


def _organization(db: Session) -> OrganizationSettings | None:
    return (
        db.query(OrganizationSettings)
        .filter(OrganizationSettings.id == 1)
        .first()
    )


def build_card(db: Session, member: Member) -> dict:
    """Assemble the card DTO for a member (name, number, status, branding, token)."""
    person = member.person
    org = _organization(db)
    full_name = f"{person.first_name} {person.last_name}".strip()
    return {
        "member_id": member.id,
        "full_name": full_name,
        "member_number": member.member_number or f"#{member.id}",
        "status": member.status,
        "photo_url": person.photo_url,
        "organization": {
            "name": org.name if org else "",
            "logo_url": org.logo_url if org else None,
            "brand_color": org.brand_color if org else None,
        },
        "token": sign_card_token(member.id),
    }


def card_qr_svg(member: Member, *, scale: int = 6, border: int = 2, inline: bool = False) -> str:
    """Render the member's signed token as an SVG QR code.

    ``inline=True`` omits the XML declaration and namespace so the SVG can be
    embedded directly in the PDF card HTML; the default produces a standalone
    document suitable for the ``image/svg+xml`` endpoint.
    """
    import segno

    qr = segno.make(sign_card_token(member.id), error="m")
    buff = io.BytesIO()
    qr.save(
        buff,
        kind="svg",
        scale=scale,
        border=border,
        xmldecl=not inline,
        svgns=not inline,
    )
    return buff.getvalue().decode("utf-8")


def _initials(full_name: str) -> str:
    parts = full_name.split()
    first = parts[0][0] if parts else ""
    last = parts[-1][0] if len(parts) > 1 else ""
    return (first + last).upper()


def _photo_data_uri(photo_url: str | None) -> str | None:
    """Resolve a stored ``/uploads/...`` photo to a base64 data URI for the PDF.

    WeasyPrint renders server-side, so the photo is embedded inline rather than
    fetched over HTTP. Returns ``None`` if there is no photo or the file is gone.
    """
    if not photo_url:
        return None
    rel = photo_url.replace("/uploads/", "", 1)
    path = Path(settings.STORAGE_LOCAL_PATH) / rel
    if not path.is_file():
        return None
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{encoded}"


def card_pdf(db: Session, member: Member) -> bytes:
    """Render a print-ready PDF of the member card via WeasyPrint."""
    # Lazy import so tests without WeasyPrint system libs can import this module.
    from weasyprint import HTML

    card = build_card(db, member)
    qr_svg = card_qr_svg(member, inline=True)
    template = _env.get_template("member_card.html")
    html_content = template.render(
        card=card,
        qr_svg=qr_svg,
        photo_data_uri=_photo_data_uri(card["photo_url"]),
        initials=_initials(card["full_name"]),
    )
    return HTML(string=html_content).write_pdf()


def verify_scan(db: Session, token: str) -> Member:
    """Decode a scanned token and return the live member record.

    Raises :class:`InvalidCardToken` on a malformed/tampered token and
    :class:`CardMemberNotFound` if the member no longer exists. Status is read
    live from the returned record, so a suspension takes effect immediately.
    """
    member_id = verify_card_token(token)
    if member_id is None:
        raise InvalidCardToken()

    member = (
        db.query(Member)
        .options(joinedload(Member.person))
        .filter(Member.id == member_id)
        .first()
    )
    if member is None:
        raise CardMemberNotFound()
    return member
