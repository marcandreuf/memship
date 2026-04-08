"""Remittance service layer — batch creation, SEPA XML generation, return import."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domains.billing.models import Receipt, Remittance, SepaMandate
from app.domains.billing.schemas import RemittanceCreate
from app.domains.billing.sepa_xml import generate_sepa_xml
from app.domains.organizations.models import OrganizationSettings


# --- Remittance Number Generation ---


def generate_remittance_number(db: Session, emission_date: date) -> str:
    """Generate the next remittance number.

    Format: REM-{year}-{sequence:04d}, annual reset.
    """
    year = emission_date.year
    count = (
        db.query(func.count(Remittance.id))
        .filter(extract("year", Remittance.emission_date) == year)
        .scalar()
    )
    sequence = count + 1
    number = f"REM-{year}-{sequence:04d}"

    # Ensure uniqueness
    while db.query(Remittance).filter(Remittance.remittance_number == number).first():
        sequence += 1
        number = f"REM-{year}-{sequence:04d}"

    return number


# --- Status Transitions ---

VALID_REMITTANCE_TRANSITIONS = {
    "draft": {"ready", "cancelled"},
    "ready": {"submitted", "cancelled"},
    "submitted": {"processed"},
    "processed": {"closed"},
    "closed": set(),
    "cancelled": set(),
}


def validate_remittance_transition(current: str, target: str) -> None:
    """Validate that a remittance status transition is allowed."""
    allowed = VALID_REMITTANCE_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition remittance from '{current}' to '{target}'",
        )


# --- CRUD ---


def create_remittance(
    db: Session, data: RemittanceCreate, created_by_id: int
) -> Remittance:
    """Create a remittance batch from a list of receipt IDs.

    Validates that all receipts are eligible (emitted/overdue, batchable,
    member has active mandate).
    """
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        raise HTTPException(status_code=500, detail="Organization settings not found")
    if not org.creditor_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization creditor ID must be configured",
        )
    if not org.bank_iban:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization bank IBAN must be configured",
        )

    # Fetch receipts
    receipts = (
        db.query(Receipt)
        .filter(
            Receipt.id.in_(data.receipt_ids),
            Receipt.is_active.is_(True),
        )
        .all()
    )

    if len(receipts) != len(data.receipt_ids):
        found_ids = {r.id for r in receipts}
        missing = set(data.receipt_ids) - found_ids
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Receipts not found: {sorted(missing)}",
        )

    # Validate each receipt
    errors = []
    member_ids = set()
    for r in receipts:
        if r.status not in ("emitted", "overdue"):
            errors.append(f"Receipt {r.receipt_number}: status '{r.status}' not eligible (must be emitted or overdue)")
        if not r.is_batchable:
            errors.append(f"Receipt {r.receipt_number}: not batchable")
        if r.remittance_id:
            errors.append(f"Receipt {r.receipt_number}: already in remittance #{r.remittance_id}")
        member_ids.add(r.member_id)

    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=errors,
        )

    # Check mandates for all members
    mandates = (
        db.query(SepaMandate)
        .filter(
            SepaMandate.member_id.in_(member_ids),
            SepaMandate.status == "active",
            SepaMandate.is_active.is_(True),
        )
        .all()
    )
    mandate_map = {}
    for m in mandates:
        # Keep the latest mandate per member
        if m.member_id not in mandate_map or m.created_at > mandate_map[m.member_id].created_at:
            mandate_map[m.member_id] = m

    members_without_mandate = member_ids - set(mandate_map.keys())
    if members_without_mandate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Members without active mandate: {sorted(members_without_mandate)}",
        )

    # Calculate total
    total = sum(Decimal(str(r.total_amount)) for r in receipts)

    # Create remittance
    today = date.today()
    remittance = Remittance(
        remittance_number=generate_remittance_number(db, today),
        remittance_type="sepa",
        status="draft",
        emission_date=today,
        due_date=data.due_date,
        total_amount=total,
        receipt_count=len(receipts),
        creditor_name=org.name,
        creditor_iban=org.bank_iban,
        creditor_bic=org.bank_bic,
        creditor_id=org.creditor_id,
        notes=data.notes,
        created_by=created_by_id,
    )
    db.add(remittance)
    db.flush()

    # Link receipts
    for r in receipts:
        r.remittance_id = remittance.id

    db.flush()
    return remittance


def generate_remittance_xml(db: Session, remittance: Remittance) -> bytes:
    """Generate SEPA XML for a remittance and save to storage.

    Transitions status to 'ready'.
    """
    if remittance.status not in ("draft", "ready"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot generate XML for remittance in '{remittance.status}' status",
        )

    receipts = (
        db.query(Receipt)
        .filter(Receipt.remittance_id == remittance.id, Receipt.is_active.is_(True))
        .all()
    )
    if not receipts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Remittance has no receipts",
        )

    # Load mandates
    member_ids = {r.member_id for r in receipts}
    mandates = (
        db.query(SepaMandate)
        .filter(
            SepaMandate.member_id.in_(member_ids),
            SepaMandate.status == "active",
            SepaMandate.is_active.is_(True),
        )
        .all()
    )
    mandate_map = {}
    for m in mandates:
        if m.member_id not in mandate_map or m.created_at > mandate_map[m.member_id].created_at:
            mandate_map[m.member_id] = m

    # Generate XML
    xml_bytes = generate_sepa_xml(remittance, receipts, mandate_map)

    # Save to storage
    year = remittance.emission_date.year
    storage_dir = Path(settings.STORAGE_LOCAL_PATH) / "remittances" / str(year)
    storage_dir.mkdir(parents=True, exist_ok=True)
    file_path = storage_dir / f"{remittance.remittance_number}.xml"
    with open(file_path, "wb") as f:
        f.write(xml_bytes)

    remittance.sepa_file_path = str(file_path)
    remittance.status = "ready"
    db.flush()

    return xml_bytes


def mark_submitted(db: Session, remittance: Remittance) -> Remittance:
    """Mark remittance as submitted to bank."""
    validate_remittance_transition(remittance.status, "submitted")
    remittance.status = "submitted"
    db.flush()
    return remittance


def import_returns(
    db: Session, remittance: Remittance, return_data: list[dict]
) -> dict:
    """Process return/rejection data for a remittance.

    Args:
        return_data: List of dicts with 'receipt_number' and 'reason'.

    Returns:
        Summary: {processed, returned, not_found}.
    """
    if remittance.status not in ("submitted", "processed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot import returns for remittance in '{remittance.status}' status",
        )

    receipts = (
        db.query(Receipt)
        .filter(Receipt.remittance_id == remittance.id, Receipt.is_active.is_(True))
        .all()
    )
    receipt_map = {r.receipt_number: r for r in receipts}

    processed = 0
    returned = 0
    not_found = 0

    for entry in return_data:
        receipt_number = entry.get("receipt_number", "")
        reason = entry.get("reason", "Returned by bank")

        receipt = receipt_map.get(receipt_number)
        if not receipt:
            not_found += 1
            continue

        processed += 1
        if receipt.status in ("emitted", "overdue"):
            receipt.status = "returned"
            receipt.return_reason = reason[:255]
            receipt.return_date = date.today()
            returned += 1

    if remittance.status == "submitted":
        remittance.status = "processed"

    db.flush()
    return {"processed": processed, "returned": returned, "not_found": not_found}


def close_remittance(db: Session, remittance: Remittance) -> Remittance:
    """Close a remittance — finalize the batch."""
    validate_remittance_transition(remittance.status, "closed")
    remittance.status = "closed"
    db.flush()
    return remittance


def cancel_remittance(db: Session, remittance: Remittance) -> Remittance:
    """Cancel a remittance — unlink all receipts."""
    validate_remittance_transition(remittance.status, "cancelled")

    receipts = (
        db.query(Receipt)
        .filter(Receipt.remittance_id == remittance.id)
        .all()
    )
    for r in receipts:
        r.remittance_id = None

    remittance.status = "cancelled"
    db.flush()
    return remittance
