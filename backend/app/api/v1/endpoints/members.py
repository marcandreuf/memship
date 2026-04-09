"""Member endpoints."""

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.authorization import require_admin
from app.core.db_utils import get_or_404
from app.core.pagination import PageMeta, paginate
from app.core.security.dependencies import get_current_user
from app.db.session import get_db
from app.domains.auth.models import User
from app.domains.members.models import Member, MembershipType
from app.domains.members.schemas import (
    GuardianResponse,
    MemberCreate,
    MemberResponse,
    MemberStatusChange,
    MemberUpdate,
    PersonResponse,
)
from app.domains.members.service import change_member_status, create_member, is_minor_by_dob
from app.domains.persons.models import Contact, ContactType, Person

router = APIRouter(prefix="/members", tags=["members"])


def _to_response(member: Member) -> MemberResponse:
    guardian = None
    if member.guardian:
        guardian = GuardianResponse.model_validate(member.guardian)

    return MemberResponse(
        id=member.id,
        person_id=member.person_id,
        person=PersonResponse.model_validate(member.person),
        membership_type_id=member.membership_type_id,
        membership_type_name=(
            member.membership_type.name if member.membership_type else None
        ),
        member_number=member.member_number,
        status=member.status,
        status_reason=member.status_reason,
        joined_at=member.joined_at,
        is_minor=member.is_minor or False,
        guardian=guardian,
        internal_notes=member.internal_notes,
        is_active=member.is_active,
        created_at=member.created_at,
    )


@router.get("/")
def list_members(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    group_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    query = (
        db.query(Member)
        .options(joinedload(Member.person), joinedload(Member.membership_type), joinedload(Member.guardian))
    )

    if group_id is not None:
        query = query.join(
            MembershipType, Member.membership_type_id == MembershipType.id
        ).filter(MembershipType.group_id == group_id)

    if search:
        search_term = f"%{search}%"
        query = query.join(Person, Member.person_id == Person.id).filter(
            (Person.first_name.ilike(search_term))
            | (Person.last_name.ilike(search_term))
            | (Person.email.ilike(search_term))
            | (Member.member_number.ilike(search_term))
        )

    if status_filter:
        query = query.filter(Member.status == status_filter)

    query = query.order_by(Member.id.desc())
    items, meta = paginate(query, page, per_page)

    return {
        "meta": meta.model_dump(),
        "items": [_to_response(m) for m in items],
    }


@router.get("/{member_id}", response_model=MemberResponse)
def get_member(
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member = (
        db.query(Member)
        .options(joinedload(Member.person), joinedload(Member.membership_type), joinedload(Member.guardian))
        .filter(Member.id == member_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Members can only view themselves
    if current_user.role == "member":
        own_member = (
            db.query(Member).filter(Member.user_id == current_user.id).first()
        )
        if not own_member or own_member.id != member_id:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

    return _to_response(member)


@router.post("/", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def create_member_endpoint(
    data: MemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    member = create_member(
        db,
        first_name=data.first_name,
        last_name=data.last_name,
        email=data.email,
        date_of_birth=data.date_of_birth,
        gender=data.gender,
        national_id=data.national_id,
        membership_type_id=data.membership_type_id,
        guardian_person_id=data.guardian_person_id,
        internal_notes=data.internal_notes,
    )
    db.commit()
    db.refresh(member)
    # Reload with relationships
    member = (
        db.query(Member)
        .options(joinedload(Member.person), joinedload(Member.membership_type), joinedload(Member.guardian))
        .filter(Member.id == member.id)
        .first()
    )
    return _to_response(member)


@router.put("/{member_id}", response_model=MemberResponse)
def update_member(
    member_id: int,
    data: MemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member = (
        db.query(Member)
        .options(joinedload(Member.person), joinedload(Member.membership_type), joinedload(Member.guardian))
        .filter(Member.id == member_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Members can only edit themselves (limited fields)
    if current_user.role == "member":
        own_member = (
            db.query(Member).filter(Member.user_id == current_user.id).first()
        )
        if not own_member or own_member.id != member_id:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

    update_data = data.model_dump(exclude_unset=True)

    # Person fields
    person_fields = {
        "first_name", "last_name", "email", "date_of_birth", "gender", "national_id"
    }
    for field in person_fields:
        if field in update_data:
            setattr(member.person, field, update_data.pop(field))

    # Recalculate is_minor if date_of_birth changed
    if "date_of_birth" in data.model_fields_set:
        member.is_minor = is_minor_by_dob(member.person.date_of_birth)

    # Member fields
    for key, value in update_data.items():
        setattr(member, key, value)

    db.commit()
    db.refresh(member)
    return _to_response(member)


@router.put("/{member_id}/status", response_model=MemberResponse)
def change_status(
    member_id: int,
    data: MemberStatusChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    member = (
        db.query(Member)
        .options(joinedload(Member.person), joinedload(Member.membership_type), joinedload(Member.guardian))
        .filter(Member.id == member_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    try:
        member = change_member_status(db, member, data.status, data.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    db.refresh(member)
    return _to_response(member)


# --- Member self-service profile ---


class ProfileUpdate(BaseModel):
    gender: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=50)


class ProfileResponse(BaseModel):
    gender: str | None = None
    phone: str | None = None


@router.get("/me/profile", response_model=ProfileResponse)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current member's editable profile fields."""
    person = current_user.person
    mobile_type = db.query(ContactType).filter(ContactType.code == "phone_mobile").first()
    phone = None
    if mobile_type:
        contact = (
            db.query(Contact)
            .filter(
                Contact.entity_type == "person",
                Contact.entity_id == person.id,
                Contact.contact_type_id == mobile_type.id,
            )
            .first()
        )
        if contact:
            phone = contact.value
    return ProfileResponse(gender=person.gender, phone=phone)


@router.put("/me/profile", response_model=ProfileResponse)
def update_my_profile(
    data: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the current member's profile (gender, phone)."""
    person = current_user.person
    update_data = data.model_dump(exclude_unset=True)

    if "gender" in update_data:
        person.gender = update_data["gender"]

    if "phone" in update_data:
        mobile_type = db.query(ContactType).filter(ContactType.code == "phone_mobile").first()
        if mobile_type:
            contact = (
                db.query(Contact)
                .filter(
                    Contact.entity_type == "person",
                    Contact.entity_id == person.id,
                    Contact.contact_type_id == mobile_type.id,
                )
                .first()
            )
            if update_data["phone"]:
                if contact:
                    contact.value = update_data["phone"]
                else:
                    db.add(Contact(
                        entity_type="person",
                        entity_id=person.id,
                        contact_type_id=mobile_type.id,
                        value=update_data["phone"],
                        is_primary=True,
                    ))
            elif contact:
                db.delete(contact)

    db.commit()

    # Re-read for response
    phone_val = None
    mobile_type = db.query(ContactType).filter(ContactType.code == "phone_mobile").first()
    if mobile_type:
        c = db.query(Contact).filter(
            Contact.entity_type == "person",
            Contact.entity_id == person.id,
            Contact.contact_type_id == mobile_type.id,
        ).first()
        if c:
            phone_val = c.value
    return ProfileResponse(gender=person.gender, phone=phone_val)


# --- Member payment method ---


class PaymentMethodUpdate(BaseModel):
    payment_method: str | None = Field(default=None, pattern=r"^(direct_debit|bank_transfer|cash|card)$")
    bank_iban: str | None = Field(default=None, max_length=34)
    bank_bic: str | None = Field(default=None, max_length=11)
    bank_holder_name: str | None = Field(default=None, max_length=255)


class PaymentMethodResponse(BaseModel):
    payment_method: str | None = None
    bank_iban: str | None = None
    bank_iban_masked: str | None = None
    bank_bic: str | None = None
    bank_holder_name: str | None = None
    mandate_status: str | None = None
    mandate_reference: str | None = None
    mandate_signed_at: str | None = None
    warnings: list[str] = []


def _mask_iban(iban: str | None) -> str | None:
    if not iban or len(iban) < 8:
        return iban
    return iban[:4] + " **** **** **** " + iban[-4:]


def _build_payment_response(person: Person, db: Session) -> PaymentMethodResponse:
    from app.domains.billing.models import SepaMandate

    warnings: list[str] = []

    # Mandate info
    member = person.member
    mandate_status = None
    mandate_reference = None
    mandate_signed_at = None
    if member:
        mandate = (
            db.query(SepaMandate)
            .filter(SepaMandate.member_id == member.id, SepaMandate.is_active.is_(True))
            .order_by(SepaMandate.created_at.desc())
            .first()
        )
        if mandate:
            mandate_status = mandate.status
            mandate_reference = mandate.mandate_reference
            mandate_signed_at = str(mandate.signed_at) if mandate.signed_at else None
        else:
            mandate_status = "none"

    # Warnings
    if person.payment_method == "direct_debit":
        if not person.bank_iban:
            warnings.append("missing_iban")
        elif not _is_valid_iban_format(person.bank_iban):
            warnings.append("invalid_iban")
        if not person.bank_bic:
            warnings.append("missing_bic")
        if mandate_status != "active":
            warnings.append("no_active_mandate")

    return PaymentMethodResponse(
        payment_method=person.payment_method,
        bank_iban=person.bank_iban,
        bank_iban_masked=_mask_iban(person.bank_iban),
        bank_bic=person.bank_bic,
        bank_holder_name=person.bank_holder_name,
        mandate_status=mandate_status,
        mandate_reference=mandate_reference,
        mandate_signed_at=mandate_signed_at,
        warnings=warnings,
    )


def _is_valid_iban_format(iban: str) -> bool:
    import re
    return bool(re.match(r"^[A-Z]{2}\d{2}[A-Z0-9]{4,30}$", iban))


@router.get("/me/payment-method", response_model=PaymentMethodResponse)
def get_my_payment_method(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current member's payment method and mandate info."""
    return _build_payment_response(current_user.person, db)


@router.put("/me/payment-method", response_model=PaymentMethodResponse)
def update_my_payment_method(
    data: PaymentMethodUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the current member's payment method."""
    person = current_user.person
    update_data = data.model_dump(exclude_unset=True)

    if "bank_iban" in update_data and update_data["bank_iban"]:
        update_data["bank_iban"] = update_data["bank_iban"].upper().replace(" ", "")

    for key, value in update_data.items():
        setattr(person, key, value)

    db.commit()
    db.refresh(person)
    return _build_payment_response(person, db)
