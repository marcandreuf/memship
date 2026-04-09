"""SEPA mandate management endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.authorization import require_admin
from app.core.config import settings
from app.core.pagination import paginate
from app.core.security.dependencies import get_current_user
from app.db.session import get_db
from app.domains.auth.models import User
from app.domains.billing.models import SepaMandate
from app.domains.billing.schemas import MandateCreate, MandateResponse, MandateUpdate
from app.domains.billing.mandate_service import (
    cancel_mandate,
    create_mandate,
    get_active_mandate,
    update_mandate,
)
from app.domains.members.models import Member

router = APIRouter(prefix="/mandates", tags=["mandates"])
member_router = APIRouter(tags=["mandates"])

ALLOWED_DOC_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
MAX_DOC_SIZE_MB = 10


@router.get("/", response_model=dict)
def list_mandates(
    member_id: int | None = None,
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all mandates with optional filters."""
    query = db.query(SepaMandate).filter(SepaMandate.is_active.is_(True))

    if member_id is not None:
        query = query.filter(SepaMandate.member_id == member_id)
    if status_filter:
        query = query.filter(SepaMandate.status == status_filter)
    if search:
        query = query.filter(
            SepaMandate.debtor_name.ilike(f"%{search}%")
            | SepaMandate.mandate_reference.ilike(f"%{search}%")
            | SepaMandate.debtor_iban.ilike(f"%{search}%")
        )

    query = query.order_by(SepaMandate.created_at.desc())
    items, meta = paginate(query, page, page_size)

    return {
        "items": [MandateResponse.model_validate(m).model_dump() for m in items],
        "meta": meta.model_dump(),
        "total": meta.total,
    }


def _enrich_document_info(mandate: SepaMandate) -> dict:
    """Build response dict with document_info from filesystem."""
    from datetime import datetime, timezone
    from app.domains.billing.schemas import DocumentInfo

    data = MandateResponse.model_validate(mandate).model_dump()
    if mandate.document_path:
        doc_path = Path(mandate.document_path)
        if doc_path.exists():
            stat = doc_path.stat()
            uploaded = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
            data["document_info"] = DocumentInfo(
                filename=doc_path.name,
                size_bytes=stat.st_size,
                uploaded_at=uploaded,
            ).model_dump()
    return data


@router.get("/{mandate_id}", response_model=MandateResponse)
def get_mandate(
    mandate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get a mandate by ID."""
    mandate = db.query(SepaMandate).filter(
        SepaMandate.id == mandate_id, SepaMandate.is_active.is_(True)
    ).first()
    if not mandate:
        raise HTTPException(status_code=404, detail="Mandate not found")
    return _enrich_document_info(mandate)


@router.post("/", response_model=MandateResponse, status_code=status.HTTP_201_CREATED)
def create_mandate_endpoint(
    data: MandateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a new SEPA mandate for a member."""
    mandate = create_mandate(db, data)
    db.commit()
    db.refresh(mandate)
    return mandate


@router.put("/{mandate_id}", response_model=MandateResponse)
def update_mandate_endpoint(
    mandate_id: int,
    data: MandateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update a mandate (only active mandates)."""
    mandate = db.query(SepaMandate).filter(
        SepaMandate.id == mandate_id, SepaMandate.is_active.is_(True)
    ).first()
    if not mandate:
        raise HTTPException(status_code=404, detail="Mandate not found")
    mandate = update_mandate(db, mandate, data)
    db.commit()
    db.refresh(mandate)
    return mandate


@router.post("/{mandate_id}/cancel", response_model=MandateResponse)
def cancel_mandate_endpoint(
    mandate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Cancel a mandate."""
    mandate = db.query(SepaMandate).filter(
        SepaMandate.id == mandate_id, SepaMandate.is_active.is_(True)
    ).first()
    if not mandate:
        raise HTTPException(status_code=404, detail="Mandate not found")
    mandate = cancel_mandate(db, mandate)
    db.commit()
    db.refresh(mandate)
    return mandate


@router.get("/{mandate_id}/pdf")
def download_mandate_pdf(
    mandate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Download a paper mandate PDF for signing."""
    mandate = db.query(SepaMandate).filter(
        SepaMandate.id == mandate_id, SepaMandate.is_active.is_(True)
    ).first()
    if not mandate:
        raise HTTPException(status_code=404, detail="Mandate not found")

    from app.domains.billing.mandate_pdf import generate_mandate_pdf

    pdf_bytes = generate_mandate_pdf(db, mandate)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{mandate.mandate_reference}.pdf"'
        },
    )


@router.post("/{mandate_id}/upload-signed", response_model=MandateResponse)
async def upload_signed_mandate(
    mandate_id: int,
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Upload a signed mandate document (PDF or image)."""
    mandate = db.query(SepaMandate).filter(
        SepaMandate.id == mandate_id, SepaMandate.is_active.is_(True)
    ).first()
    if not mandate:
        raise HTTPException(status_code=404, detail="Mandate not found")

    # Validate extension
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else ""
    if ext not in ALLOWED_DOC_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File type not allowed. Accepted: {', '.join(ALLOWED_DOC_EXTENSIONS)}",
        )

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_DOC_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max {MAX_DOC_SIZE_MB} MB",
        )

    # Save to storage
    storage_dir = Path(settings.STORAGE_LOCAL_PATH) / "mandates" / str(mandate.member_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{mandate.mandate_reference}.{ext}"
    file_path = storage_dir / filename
    with open(file_path, "wb") as f:
        f.write(content)

    mandate.document_path = str(file_path)
    db.commit()
    db.refresh(mandate)
    return mandate


# --- Member self-view ---


@member_router.get("/members/me/mandate", response_model=MandateResponse | None)
def get_my_mandate(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current member's active mandate (read-only)."""
    member = (
        db.query(Member)
        .filter(Member.person_id == current_user.person_id, Member.is_active.is_(True))
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    mandate = get_active_mandate(db, member.id)
    if not mandate:
        return Response(status_code=204)
    return mandate
