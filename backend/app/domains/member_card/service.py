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


class CardNotIssued(Exception):
    """A valid token for a member whose type no longer issues a card.

    Distinct from ``CardMemberNotFound`` on purpose: at the door, "this member
    does not exist" and "this card is no longer valid" are different facts and
    the second is the actionable one (#428 Part 2).
    """


class CardMemberNotFound(Exception):
    """The token is valid but the referenced member no longer exists."""


def _organization(db: Session) -> OrganizationSettings | None:
    return (
        db.query(OrganizationSettings)
        .filter(OrganizationSettings.id == 1)
        .first()
    )


def member_is_issued_a_card(member: Member) -> bool:
    """Whether this member's membership type issues a card (#428 Part 2).

    The single definition, because it is asked in four different shapes — the
    member's own card, an admin printing someone else's, the scan at the door,
    and whether the portal shows the menu item at all — and four copies of it
    would drift.

    **A member with no type is not issued one.** `membership_type_id` is
    nullable, so this is a real case rather than a broken row. The policy is
    expressed per type and starts off for every type, so a member with no type
    has no type whose switch was turned on. The permissive reading would be the
    one loophole in a feature whose whole purpose is withholding: every *typed*
    member would wait for an admin to tick their type while a member with no
    type got a card immediately. It matches the same call on per-type pricing,
    where a restriction naming types cannot include a member who has none.

    Independent of `features.member_card`, which the endpoints check separately:
    that flag decides whether the module exists on this instance at all.
    """
    return bool(member.membership_type and member.membership_type.issues_card)


def member_card_available(db: Session, member: Member | None) -> bool:
    """Both levels at once, for callers that need a yes/no rather than a 404.

    The endpoints check the two separately — ``_require_card_enabled`` for the
    instance flag, ``_require_card_for`` for the type — because each raises.
    This is the same question for the portal, which needs to decide whether to
    offer the menu item at all; without it the navigation would have to probe an
    endpoint whose whole job is to answer 404.

    ``None`` for a staff account with no member record: it has no card, and no
    type to consult.
    """
    if member is None:
        return False
    org = _organization(db)
    if not ((org.features or {}) if org else {}).get("member_card"):
        return False
    return member_is_issued_a_card(member)


def build_card(db: Session, member: Member) -> dict:
    """Assemble the card DTO for a member (name, number, type, status, branding, token).

    ``membership_type`` is the type's name, or ``None``. It is nullable in the
    column (`ondelete="SET NULL"`), so a staff-created record or one whose type
    was deleted legitimately has none, and each surface decides how to render
    that rather than printing an empty label (#428).
    """
    person = member.person
    org = _organization(db)
    full_name = f"{person.first_name} {person.last_name}".strip()
    return {
        "member_id": member.id,
        "full_name": full_name,
        "member_number": member.member_number or f"#{member.id}",
        "membership_type": member.membership_type.name if member.membership_type else None,
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
        .options(joinedload(Member.person), joinedload(Member.membership_type))
        .filter(Member.id == member_id)
        .first()
    )
    if member is None:
        raise CardMemberNotFound()
    # Re-read the type live, not only the status. A token is signed once and
    # never expires, so a QR captured while the holder's type still issued
    # cards would keep verifying at the door after an admin switched that type
    # off — which would make the switch advisory. The issue calls this out as
    # the consequence easiest to miss (#428 Part 2).
    if not member_is_issued_a_card(member):
        raise CardNotIssued()
    return member
