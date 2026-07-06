"""Member card endpoints — digital card, QR, PDF (member) and scan (admin).

Card/QR/PDF endpoints return 404 when ``features.member_card`` is off — a
deliberate backend gate (beyond frontend-only gating) appropriate for a
verification tool.
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session, joinedload

from app.core.authorization import require_admin
from app.core.security.dependencies import get_current_user
from app.db.session import get_db
from app.domains.auth.models import User
from app.domains.member_card.schemas import (
    CardResponse,
    ScanRequest,
    ScanResponse,
)
from app.domains.member_card.service import (
    CardMemberNotFound,
    InvalidCardToken,
    build_card,
    card_pdf,
    card_qr_svg,
    verify_scan,
)
from app.domains.members.models import Member
from app.domains.organizations.models import OrganizationSettings

router = APIRouter(tags=["member-card"])


def _require_card_enabled(db: Session) -> None:
    org = (
        db.query(OrganizationSettings)
        .filter(OrganizationSettings.id == 1)
        .first()
    )
    features = (org.features or {}) if org else {}
    if not features.get("member_card"):
        raise HTTPException(status_code=404, detail="Not found")


def _current_member(db: Session, user: User) -> Member:
    member = (
        db.query(Member)
        .options(joinedload(Member.person))
        .filter(Member.user_id == user.id)
        .first()
    )
    if member is None:
        raise HTTPException(status_code=403, detail="No member profile")
    return member


def _load_member_or_404(db: Session, member_id: int) -> Member:
    member = (
        db.query(Member)
        .options(joinedload(Member.person))
        .filter(Member.id == member_id)
        .first()
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    return member


def _pdf_response(db: Session, member: Member) -> Response:
    pdf = card_pdf(db, member)
    filename = f"member-card-{member.member_number or member.id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _qr_response(member: Member) -> Response:
    return Response(
        content=card_qr_svg(member),
        media_type="image/svg+xml",
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.get("/me/card", response_model=CardResponse)
def get_my_card(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_card_enabled(db)
    member = _current_member(db, current_user)
    return build_card(db, member)


@router.get("/me/card/qr.svg")
def get_my_card_qr(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_card_enabled(db)
    member = _current_member(db, current_user)
    return _qr_response(member)


@router.get("/me/card/pdf")
def get_my_card_pdf(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_card_enabled(db)
    member = _current_member(db, current_user)
    return _pdf_response(db, member)


@router.post("/card/scan", response_model=ScanResponse)
def scan_card(
    data: ScanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    _require_card_enabled(db)
    try:
        member = verify_scan(db, data.token)
    except InvalidCardToken:
        raise HTTPException(status_code=400, detail="Invalid card code")
    except CardMemberNotFound:
        raise HTTPException(status_code=404, detail="Member not found")

    person = member.person
    return ScanResponse(
        member_id=member.id,
        full_name=f"{person.first_name} {person.last_name}".strip(),
        member_number=member.member_number or f"#{member.id}",
        status=member.status,
        photo_url=person.photo_url,
    )


# --- Admin: view/print any member's card (from the member detail page) ---


@router.get("/members/{member_id}/card", response_model=CardResponse)
def get_member_card_admin(
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    _require_card_enabled(db)
    member = _load_member_or_404(db, member_id)
    return build_card(db, member)


@router.get("/members/{member_id}/card/qr.svg")
def get_member_card_qr_admin(
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    _require_card_enabled(db)
    member = _load_member_or_404(db, member_id)
    return _qr_response(member)


@router.get("/members/{member_id}/card/pdf")
def get_member_card_pdf_admin(
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    _require_card_enabled(db)
    member = _load_member_or_404(db, member_id)
    return _pdf_response(db, member)
