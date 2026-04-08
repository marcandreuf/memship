"""Mandate service layer — SEPA mandate CRUD, reference generation, status transitions."""

import re
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domains.billing.models import SepaMandate
from app.domains.billing.schemas import MandateCreate, MandateUpdate
from app.domains.members.models import Member
from app.domains.organizations.models import OrganizationSettings


# --- IBAN Validation ---

IBAN_PATTERN = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{4,30}$")


def validate_iban_format(iban: str) -> bool:
    """Basic IBAN format validation (structure only, not checksum)."""
    return bool(IBAN_PATTERN.match(iban))


# --- Mandate Reference Generation ---


def generate_mandate_reference(db: Session, member: Member) -> str:
    """Generate a unique mandate reference.

    Format: {ORG_PREFIX}-{MEMBER_NUMBER}-{SEQ}
    Max 35 chars, SEPA-compliant: [A-Za-z0-9+/-]
    """
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    prefix = (org.invoice_prefix or "MEM")[:5]

    # Pad member number or use member ID
    member_part = member.member_number or f"{member.id:05d}"
    # Sanitize: only keep SEPA-allowed characters
    member_part = re.sub(r"[^A-Za-z0-9+/\-]", "", member_part)[:10]

    # Count existing mandates for this member to get sequence
    count = (
        db.query(func.count(SepaMandate.id))
        .filter(SepaMandate.member_id == member.id)
        .scalar()
    )
    seq = count + 1

    reference = f"{prefix}-{member_part}-{seq:03d}"

    # Ensure uniqueness
    while db.query(SepaMandate).filter(SepaMandate.mandate_reference == reference).first():
        seq += 1
        reference = f"{prefix}-{member_part}-{seq:03d}"

    return reference[:35]


# --- Status Transitions ---

VALID_MANDATE_TRANSITIONS = {
    "active": {"cancelled", "expired"},
    "cancelled": set(),
    "expired": set(),
}


def validate_mandate_transition(current: str, target: str) -> None:
    """Validate that a mandate status transition is allowed."""
    allowed = VALID_MANDATE_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition mandate from '{current}' to '{target}'",
        )


# --- CRUD ---


def create_mandate(db: Session, data: MandateCreate) -> SepaMandate:
    """Create a new SEPA mandate for a member."""
    # Validate member exists
    member = db.query(Member).filter(Member.id == data.member_id, Member.is_active.is_(True)).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    # Validate IBAN format
    if not validate_iban_format(data.debtor_iban):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid IBAN format",
        )

    # Get org creditor_id
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org or not org.creditor_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization creditor ID must be configured before creating mandates",
        )

    # Generate reference
    reference = generate_mandate_reference(db, member)

    mandate = SepaMandate(
        member_id=data.member_id,
        mandate_reference=reference,
        creditor_id=org.creditor_id,
        debtor_name=data.debtor_name,
        debtor_iban=data.debtor_iban,
        debtor_bic=data.debtor_bic,
        mandate_type=data.mandate_type,
        signature_method=data.signature_method,
        status="active",
        signed_at=data.signed_at,
        notes=data.notes,
    )
    db.add(mandate)
    db.flush()
    return mandate


def update_mandate(db: Session, mandate: SepaMandate, data: MandateUpdate) -> SepaMandate:
    """Update a mandate (only active mandates can be updated)."""
    if mandate.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only active mandates can be updated",
        )

    update_data = data.model_dump(exclude_unset=True)

    if "debtor_iban" in update_data and not validate_iban_format(update_data["debtor_iban"]):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid IBAN format",
        )

    for key, value in update_data.items():
        setattr(mandate, key, value)

    db.flush()
    return mandate


def cancel_mandate(db: Session, mandate: SepaMandate) -> SepaMandate:
    """Cancel a mandate."""
    validate_mandate_transition(mandate.status, "cancelled")
    mandate.status = "cancelled"
    mandate.cancelled_at = datetime.now(timezone.utc)
    db.flush()
    return mandate


def get_active_mandate(db: Session, member_id: int) -> SepaMandate | None:
    """Get the most recent active mandate for a member."""
    return (
        db.query(SepaMandate)
        .filter(
            SepaMandate.member_id == member_id,
            SepaMandate.status == "active",
            SepaMandate.is_active.is_(True),
        )
        .order_by(SepaMandate.created_at.desc())
        .first()
    )
