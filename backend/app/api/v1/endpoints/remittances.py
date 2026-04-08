"""Remittance (SEPA batch) management endpoints."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.authorization import require_admin
from app.core.pagination import paginate
from app.db.session import get_db
from app.domains.auth.models import User
from app.domains.billing.models import Receipt, Remittance
from app.domains.billing.schemas import (
    RemittanceCreate,
    RemittanceDetailResponse,
    RemittanceResponse,
    ReceiptResponse,
)
from app.domains.billing.remittance_service import (
    cancel_remittance,
    close_remittance,
    create_remittance,
    generate_remittance_xml,
    import_returns,
    mark_submitted,
)

router = APIRouter(prefix="/remittances", tags=["remittances"])


@router.get("/", response_model=dict)
def list_remittances(
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List remittances with optional status filter."""
    query = db.query(Remittance).filter(Remittance.is_active.is_(True))

    if status_filter:
        query = query.filter(Remittance.status == status_filter)

    query = query.order_by(Remittance.created_at.desc())
    items, meta = paginate(query, page, page_size)

    return {
        "items": [RemittanceResponse.model_validate(r).model_dump() for r in items],
        "meta": meta.model_dump(),
        "total": meta.total,
    }


@router.get("/{remittance_id}", response_model=RemittanceDetailResponse)
def get_remittance(
    remittance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get remittance detail with receipt list."""
    remittance = db.query(Remittance).filter(
        Remittance.id == remittance_id, Remittance.is_active.is_(True)
    ).first()
    if not remittance:
        raise HTTPException(status_code=404, detail="Remittance not found")

    receipts = (
        db.query(Receipt)
        .filter(Receipt.remittance_id == remittance.id, Receipt.is_active.is_(True))
        .all()
    )

    data = RemittanceResponse.model_validate(remittance).model_dump()
    data["receipts"] = [ReceiptResponse.model_validate(r).model_dump() for r in receipts]
    return data


@router.post("/", response_model=RemittanceResponse, status_code=status.HTTP_201_CREATED)
def create_remittance_endpoint(
    data: RemittanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a remittance batch from receipt IDs."""
    remittance = create_remittance(db, data, current_user.id)
    db.commit()
    db.refresh(remittance)
    return remittance


@router.post("/{remittance_id}/generate-xml", response_model=RemittanceResponse)
def generate_xml_endpoint(
    remittance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Generate SEPA XML file for a remittance."""
    remittance = db.query(Remittance).filter(
        Remittance.id == remittance_id, Remittance.is_active.is_(True)
    ).first()
    if not remittance:
        raise HTTPException(status_code=404, detail="Remittance not found")

    generate_remittance_xml(db, remittance)
    db.commit()
    db.refresh(remittance)
    return remittance


@router.get("/{remittance_id}/download-xml")
def download_xml(
    remittance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Download the generated SEPA XML file."""
    remittance = db.query(Remittance).filter(
        Remittance.id == remittance_id, Remittance.is_active.is_(True)
    ).first()
    if not remittance:
        raise HTTPException(status_code=404, detail="Remittance not found")
    if not remittance.sepa_file_path:
        raise HTTPException(status_code=404, detail="XML file not yet generated")

    file_path = Path(remittance.sepa_file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="XML file not found on disk")

    content = file_path.read_bytes()
    return Response(
        content=content,
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="{remittance.remittance_number}.xml"'
        },
    )


@router.post("/{remittance_id}/mark-submitted", response_model=RemittanceResponse)
def mark_submitted_endpoint(
    remittance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Mark remittance as submitted to bank."""
    remittance = db.query(Remittance).filter(
        Remittance.id == remittance_id, Remittance.is_active.is_(True)
    ).first()
    if not remittance:
        raise HTTPException(status_code=404, detail="Remittance not found")

    remittance = mark_submitted(db, remittance)
    db.commit()
    db.refresh(remittance)
    return remittance


@router.post("/{remittance_id}/import-returns")
async def import_returns_endpoint(
    remittance_id: int,
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Import return/rejection file for a remittance.

    Accepts a JSON file with format:
    [{"receipt_number": "FAC-2026-0001", "reason": "Insufficient funds"}, ...]
    """
    remittance = db.query(Remittance).filter(
        Remittance.id == remittance_id, Remittance.is_active.is_(True)
    ).first()
    if not remittance:
        raise HTTPException(status_code=404, detail="Remittance not found")

    content = await file.read()
    try:
        return_data = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid JSON file",
        )

    if not isinstance(return_data, list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Expected a JSON array of return entries",
        )

    result = import_returns(db, remittance, return_data)
    db.commit()
    return result


@router.post("/{remittance_id}/close", response_model=RemittanceResponse)
def close_remittance_endpoint(
    remittance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Close a remittance — finalize the batch."""
    remittance = db.query(Remittance).filter(
        Remittance.id == remittance_id, Remittance.is_active.is_(True)
    ).first()
    if not remittance:
        raise HTTPException(status_code=404, detail="Remittance not found")

    remittance = close_remittance(db, remittance)
    db.commit()
    db.refresh(remittance)
    return remittance


@router.post("/{remittance_id}/cancel", response_model=RemittanceResponse)
def cancel_remittance_endpoint(
    remittance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Cancel a remittance — unlink all receipts."""
    remittance = db.query(Remittance).filter(
        Remittance.id == remittance_id, Remittance.is_active.is_(True)
    ).first()
    if not remittance:
        raise HTTPException(status_code=404, detail="Remittance not found")

    remittance = cancel_remittance(db, remittance)
    db.commit()
    db.refresh(remittance)
    return remittance


@router.get("/{remittance_id}/stats")
def remittance_stats(
    remittance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get stats for a remittance batch."""
    remittance = db.query(Remittance).filter(
        Remittance.id == remittance_id, Remittance.is_active.is_(True)
    ).first()
    if not remittance:
        raise HTTPException(status_code=404, detail="Remittance not found")

    receipts = (
        db.query(Receipt)
        .filter(Receipt.remittance_id == remittance.id, Receipt.is_active.is_(True))
        .all()
    )

    status_counts = {}
    for r in receipts:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1

    return {
        "remittance_id": remittance.id,
        "remittance_number": remittance.remittance_number,
        "total_receipts": len(receipts),
        "total_amount": str(remittance.total_amount),
        "status_counts": status_counts,
    }
