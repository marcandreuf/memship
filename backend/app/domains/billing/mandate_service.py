"""Mandate service layer — SEPA mandate CRUD, reference generation, status transitions."""

import re
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domains.billing.models import SepaMandate
from app.domains.billing.schemas import (
    MandateCreate,
    MandateUpdate,
    validate_iban_format,
)
from app.domains.members.models import Member
from app.domains.persons.models import Party
from app.domains.organizations.models import OrganizationSettings


# --- Mandate Reference Generation ---


def generate_mandate_reference(db: Session, party) -> str:
    """Generate a unique mandate reference.

    Format: {ORG_PREFIX}-{IDENTIFIER}-{SEQ}
    Max 35 chars, SEPA-compliant: [A-Za-z0-9+/-]

    The identifier is the member number when the party is a member, else the
    party id zero-padded: a mandate can be signed by any legal entity (ADR
    0003), not only a member.
    """
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    prefix = (org.invoice_prefix or "MEM")[:5]

    member = (
        db.query(Member)
        .filter(Member.party_id == party.id)
        .order_by(Member.is_active.desc(), Member.id.desc())
        .first()
    )
    identifier = (member.member_number if member else None) or f"{party.id:05d}"
    # Sanitize: only keep SEPA-allowed characters
    identifier = re.sub(r"[^A-Za-z0-9+/\-]", "", identifier)[:10]

    # Count existing mandates for this party to get sequence
    count = (
        db.query(func.count(SepaMandate.id))
        .filter(SepaMandate.party_id == party.id)
        .scalar()
    )
    seq = count + 1

    reference = f"{prefix}-{identifier}-{seq:03d}"

    # Ensure uniqueness
    while db.query(SepaMandate).filter(SepaMandate.mandate_reference == reference).first():
        seq += 1
        reference = f"{prefix}-{identifier}-{seq:03d}"

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
    """Create a new SEPA mandate for a party (member or not)."""
    # Validate the party exists
    party = db.query(Party).filter(Party.id == data.party_id).first()
    if not party:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Party not found")

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

    # One active mandate per member. The database makes a second one
    # unrepresentable (#394); this is the same refusal with a message, so the
    # admin is told which mandate to cancel rather than meeting an integrity
    # error. A member changing bank account cancels the old mandate and signs
    # a new one, which is what the paperwork does too.
    existing = (
        db.query(SepaMandate)
        .filter(
            SepaMandate.party_id == party.id,
            SepaMandate.status == "active",
            SepaMandate.is_active.is_(True),
        )
        .order_by(SepaMandate.created_at.desc(), SepaMandate.id.desc())
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "member_already_has_mandate",
                "mandate_reference": existing.mandate_reference,
                "debtor_iban": existing.debtor_iban,
            },
        )

    # Generate reference
    reference = generate_mandate_reference(db, party)

    mandate = SepaMandate(
        party_id=party.id,
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


def get_active_mandate(db: Session, party_id: int) -> SepaMandate | None:
    """Get the most recent active mandate for a party."""
    return (
        db.query(SepaMandate)
        .filter(
            SepaMandate.party_id == party_id,
            SepaMandate.status == "active",
            SepaMandate.is_active.is_(True),
        )
        .order_by(SepaMandate.created_at.desc(), SepaMandate.id.desc())
        .first()
    )
