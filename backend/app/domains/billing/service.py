"""Billing service layer — receipt creation, numbering, status transitions, fee generation."""

from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.domains.billing.models import Concept, Receipt
from app.domains.billing.schemas import (
    GenerateMembershipFeesRequest,
    ReceiptCreate,
    ReceiptPayRequest,
    ReceiptReturnRequest,
    ReceiptUpdate,
)
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


# --- VAT Calculation ---


def calculate_vat(base_amount: Decimal, vat_rate: Decimal) -> tuple[Decimal, Decimal]:
    """Calculate VAT amount and total from base and rate.

    Returns (vat_amount, total_amount).
    """
    vat_amount = (base_amount * vat_rate / Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    total_amount = base_amount + vat_amount
    return vat_amount, total_amount


# --- Receipt Number Generation ---


def generate_receipt_number(db: Session, emission_date: date) -> str:
    """Generate the next receipt number.

    Format: {prefix}-{year}-{sequence:04d}
    If annual reset is enabled, sequence resets per year.
    Thread-safe via SELECT ... FOR UPDATE on org settings.
    """
    org = (
        db.query(OrganizationSettings)
        .filter(OrganizationSettings.id == 1)
        .with_for_update()
        .first()
    )
    if not org:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Organization settings not found",
        )

    prefix = org.invoice_prefix or "FAC"
    year = emission_date.year
    annual_reset = org.invoice_annual_reset if org.invoice_annual_reset is not None else True

    if annual_reset:
        # Count existing receipts for this year to determine next number
        count = (
            db.query(func.count(Receipt.id))
            .filter(
                extract("year", Receipt.emission_date) == year,
                Receipt.is_active.is_(True),
            )
            .scalar()
        )
        sequence = count + 1
    else:
        # Global sequential — use org counter
        sequence = org.invoice_next_number or 1
        org.invoice_next_number = sequence + 1

    receipt_number = f"{prefix}-{year}-{sequence:04d}"

    # Ensure uniqueness (safety net)
    while db.query(Receipt).filter(Receipt.receipt_number == receipt_number).first():
        sequence += 1
        receipt_number = f"{prefix}-{year}-{sequence:04d}"

    return receipt_number


# --- Status Transitions ---

VALID_TRANSITIONS = {
    "new": {"pending", "emitted", "cancelled"},
    "pending": {"emitted", "cancelled", "overdue"},
    "emitted": {"paid", "returned", "cancelled", "overdue"},
    "overdue": {"paid", "returned", "cancelled"},
    "returned": {"pending", "cancelled"},
    "paid": set(),
    "cancelled": set(),
}


def validate_status_transition(current: str, target: str) -> None:
    """Validate that a receipt status transition is allowed."""
    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition from '{current}' to '{target}'",
        )


# --- Receipt CRUD ---


def create_receipt(
    db: Session, data: ReceiptCreate, created_by_id: int
) -> Receipt:
    """Create a new receipt with calculated VAT."""
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    vat_rate = Decimal(str(data.vat_rate))
    base_amount = Decimal(str(data.base_amount))

    # Apply discount
    discount_amount = Decimal(str(data.discount_amount or 0))
    if data.discount_type == "percentage" and discount_amount > 0:
        discount_amount = (base_amount * discount_amount / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    effective_base = base_amount - discount_amount
    if effective_base < 0:
        effective_base = Decimal("0")

    vat_amount, total_amount = calculate_vat(effective_base, vat_rate)

    receipt_number = generate_receipt_number(db, data.emission_date)

    receipt = Receipt(
        receipt_number=receipt_number,
        member_id=data.member_id,
        concept_id=data.concept_id,
        registration_id=data.registration_id,
        origin=data.origin,
        description=data.description,
        base_amount=effective_base,
        vat_rate=vat_rate,
        vat_amount=vat_amount,
        total_amount=total_amount,
        discount_amount=discount_amount if data.discount_amount else Decimal("0"),
        discount_type=data.discount_type,
        status="pending",
        emission_date=data.emission_date,
        due_date=data.due_date,
        billing_period_start=data.billing_period_start,
        billing_period_end=data.billing_period_end,
        notes=data.notes,
        is_batchable=data.is_batchable,
        created_by=created_by_id,
    )
    db.add(receipt)
    db.flush()
    return receipt


def update_receipt(db: Session, receipt: Receipt, data: ReceiptUpdate) -> Receipt:
    """Update a receipt (only allowed in 'new' or 'pending' status)."""
    if receipt.status not in ("new", "pending"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only edit receipts in 'new' or 'pending' status",
        )

    update_data = data.model_dump(exclude_unset=True)

    # Recalculate amounts if base or vat changed
    recalculate = "base_amount" in update_data or "vat_rate" in update_data
    for key, value in update_data.items():
        setattr(receipt, key, value)

    if recalculate:
        base = Decimal(str(receipt.base_amount))
        vat_rate = Decimal(str(receipt.vat_rate))
        receipt.vat_amount, receipt.total_amount = calculate_vat(base, vat_rate)

    db.flush()
    return receipt


def emit_receipt(db: Session, receipt: Receipt) -> Receipt:
    """Emit a receipt — transition to 'emitted' status."""
    validate_status_transition(receipt.status, "emitted")
    receipt.status = "emitted"
    db.flush()
    return receipt


def pay_receipt(
    db: Session, receipt: Receipt, data: ReceiptPayRequest
) -> Receipt:
    """Mark a receipt as paid."""
    validate_status_transition(receipt.status, "paid")
    receipt.status = "paid"
    receipt.payment_method = data.payment_method
    receipt.payment_date = data.payment_date or date.today()
    db.flush()
    return receipt


def return_receipt(
    db: Session, receipt: Receipt, data: ReceiptReturnRequest
) -> Receipt:
    """Mark a receipt as returned (rejected by bank)."""
    validate_status_transition(receipt.status, "returned")
    receipt.status = "returned"
    receipt.return_reason = data.return_reason
    receipt.return_date = data.return_date or date.today()
    db.flush()
    return receipt


def cancel_receipt(db: Session, receipt: Receipt) -> Receipt:
    """Cancel a receipt."""
    validate_status_transition(receipt.status, "cancelled")
    receipt.status = "cancelled"
    db.flush()
    return receipt


def reemit_receipt(db: Session, receipt: Receipt) -> Receipt:
    """Re-emit a returned receipt — moves back to 'pending'."""
    validate_status_transition(receipt.status, "pending")
    receipt.status = "pending"
    receipt.return_date = None
    receipt.return_reason = None
    db.flush()
    return receipt


# --- Fee Generation ---


def generate_membership_fees(
    db: Session, data: GenerateMembershipFeesRequest, created_by_id: int
) -> list[Receipt]:
    """Bulk generate membership fee receipts for all active members.

    Creates one receipt per active member based on their membership type's base_price.
    Skips members who already have a receipt for the same billing period.
    """
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    default_vat = Decimal(str(org.default_vat_rate or 21))

    # Get all active members with their membership type
    members = (
        db.query(Member, MembershipType, Person)
        .join(MembershipType, Member.membership_type_id == MembershipType.id)
        .join(Person, Member.person_id == Person.id)
        .filter(
            Member.status == "active",
            Member.is_active.is_(True),
            MembershipType.base_price > 0,
        )
        .all()
    )

    # Find or create membership concepts per membership type
    concept_cache: dict[int, Concept] = {}
    receipts: list[Receipt] = []

    for member, mtype, person in members:
        # Skip if receipt already exists for this period
        existing = (
            db.query(Receipt)
            .filter(
                Receipt.member_id == member.id,
                Receipt.origin == "membership",
                Receipt.billing_period_start == data.billing_period_start,
                Receipt.billing_period_end == data.billing_period_end,
                Receipt.is_active.is_(True),
                Receipt.status != "cancelled",
            )
            .first()
        )
        if existing:
            continue

        # Get or create concept for this membership type
        if mtype.id not in concept_cache:
            concept = (
                db.query(Concept)
                .filter(
                    Concept.code == f"membership-{mtype.slug}",
                    Concept.is_active.is_(True),
                )
                .first()
            )
            if not concept:
                concept = Concept(
                    name=f"{mtype.name}",
                    code=f"membership-{mtype.slug}",
                    concept_type="membership",
                    default_amount=mtype.base_price,
                    vat_rate=default_vat,
                )
                db.add(concept)
                db.flush()
            concept_cache[mtype.id] = concept

        concept = concept_cache[mtype.id]
        base_amount = Decimal(str(mtype.base_price))
        vat_rate = Decimal(str(concept.vat_rate))
        vat_amount, total_amount = calculate_vat(base_amount, vat_rate)

        receipt_number = generate_receipt_number(db, data.emission_date)

        receipt = Receipt(
            receipt_number=receipt_number,
            member_id=member.id,
            concept_id=concept.id,
            origin="membership",
            description=f"{mtype.name} — {person.first_name} {person.last_name}",
            base_amount=base_amount,
            vat_rate=vat_rate,
            vat_amount=vat_amount,
            total_amount=total_amount,
            status="pending",
            emission_date=data.emission_date,
            due_date=data.due_date,
            billing_period_start=data.billing_period_start,
            billing_period_end=data.billing_period_end,
            is_batchable=True,
            created_by=created_by_id,
        )
        db.add(receipt)
        db.flush()
        receipts.append(receipt)

    return receipts


def generate_activity_receipt(
    db: Session,
    registration_id: int,
    member_id: int,
    activity_name: str,
    amount: Decimal,
    tax_rate: Decimal | None,
    created_by_id: int | None = None,
) -> Receipt:
    """Create a receipt for an activity registration.

    Called automatically when a registration is confirmed.
    """
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    vat_rate = tax_rate if tax_rate is not None and tax_rate > 0 else Decimal(str(org.default_vat_rate or 21))

    if amount <= 0:
        return None  # No receipt for free activities

    # Find or create activity concept
    concept = (
        db.query(Concept)
        .filter(Concept.code == "activity-registration", Concept.is_active.is_(True))
        .first()
    )
    if not concept:
        concept = Concept(
            name="Activity Registration",
            code="activity-registration",
            concept_type="activity",
            default_amount=Decimal("0"),
            vat_rate=vat_rate,
        )
        db.add(concept)
        db.flush()

    base_amount = Decimal(str(amount))
    vat_amount, total_amount = calculate_vat(base_amount, vat_rate)
    today = date.today()

    receipt_number = generate_receipt_number(db, today)

    receipt = Receipt(
        receipt_number=receipt_number,
        member_id=member_id,
        concept_id=concept.id,
        registration_id=registration_id,
        origin="activity",
        description=activity_name,
        base_amount=base_amount,
        vat_rate=vat_rate,
        vat_amount=vat_amount,
        total_amount=total_amount,
        status="emitted",
        emission_date=today,
        is_batchable=True,
        created_by=created_by_id,
    )
    db.add(receipt)
    db.flush()
    return receipt
