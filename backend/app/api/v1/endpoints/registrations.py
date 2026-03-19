"""Registration endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.authorization import require_admin
from app.core.pagination import paginate
from app.core.security.dependencies import get_current_user
from app.db.session import get_db
from app.domains.activities.eligibility import check_eligibility
from app.domains.activities.models import Activity, Registration
from app.domains.activities.registration_schemas import (
    AdminStatusChangeRequest,
    CancelRegistrationRequest,
    EligibilityResponse,
    RegisterRequest,
    RegistrationActivityInfo,
    RegistrationDetailResponse,
    RegistrationMemberInfo,
    RegistrationResponse,
)
from app.domains.activities.registration_service import (
    RegistrationError,
    admin_change_status,
    cancel_registration,
    check_self_cancellation_allowed,
    register_member,
)
from app.domains.auth.models import User
from app.domains.members.models import Member

router = APIRouter(tags=["registrations"])


def _get_activity_or_404(db: Session, activity_id: int) -> Activity:
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity


def _get_member_for_user(db: Session, user: User) -> Member:
    member = db.query(Member).filter(Member.user_id == user.id).first()
    if not member:
        raise HTTPException(status_code=400, detail="No member profile found")
    return member


def _to_detail_response(registration: Registration) -> RegistrationDetailResponse:
    member_info = None
    if registration.member and registration.member.person:
        member_info = RegistrationMemberInfo(
            id=registration.member.id,
            member_number=registration.member.member_number,
            first_name=registration.member.person.first_name,
            last_name=registration.member.person.last_name,
            email=registration.member.person.email,
        )

    return RegistrationDetailResponse(
        id=registration.id,
        activity_id=registration.activity_id,
        member_id=registration.member_id,
        modality_id=registration.modality_id,
        price_id=registration.price_id,
        status=registration.status,
        registration_data=registration.registration_data or {},
        member_notes=registration.member_notes,
        admin_notes=registration.admin_notes,
        cancelled_at=registration.cancelled_at,
        cancelled_reason=registration.cancelled_reason,
        created_at=registration.created_at,
        member=member_info,
    )


# --- Activity-scoped endpoints ---


@router.get("/activities/{activity_id}/registrations/")
def list_activity_registrations(
    activity_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List registrations for an activity (admin only)."""
    _get_activity_or_404(db, activity_id)

    query = (
        db.query(Registration)
        .filter(Registration.activity_id == activity_id)
        .options(
            joinedload(Registration.member).joinedload(Member.person),
        )
    )

    if status_filter:
        query = query.filter(Registration.status == status_filter)

    query = query.order_by(Registration.created_at.desc())
    items, meta = paginate(query, page, per_page)

    return {
        "meta": meta.model_dump(),
        "items": [_to_detail_response(r) for r in items],
    }


@router.post(
    "/activities/{activity_id}/register",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_for_activity(
    activity_id: int,
    data: RegisterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Register current user's member for an activity."""
    activity = _get_activity_or_404(db, activity_id)
    member = _get_member_for_user(db, current_user)

    try:
        registration = register_member(
            db,
            activity=activity,
            member=member,
            price_id=data.price_id,
            modality_id=data.modality_id,
            discount_code=data.discount_code,
            consents=data.consents,
            registration_data=data.registration_data,
            member_notes=data.member_notes,
        )
        db.commit()
        db.refresh(registration)
        return RegistrationResponse.model_validate(registration)
    except RegistrationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/activities/{activity_id}/eligibility",
    response_model=EligibilityResponse,
)
def check_activity_eligibility(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check if current user is eligible to register."""
    activity = _get_activity_or_404(db, activity_id)
    member = _get_member_for_user(db, current_user)

    result = check_eligibility(db, activity, member)
    return EligibilityResponse(eligible=result.eligible, reasons=result.reasons)


# --- Registration-level endpoints ---


@router.delete(
    "/registrations/{registration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def cancel_own_registration(
    registration_id: int,
    data: CancelRegistrationRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a registration (own or admin)."""
    registration = (
        db.query(Registration)
        .options(
            joinedload(Registration.activity),
            joinedload(Registration.modality),
            joinedload(Registration.price),
        )
        .filter(Registration.id == registration_id)
        .first()
    )
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")

    is_admin = current_user.role in ("admin", "super_admin")

    # Check ownership if not admin
    if not is_admin:
        member = _get_member_for_user(db, current_user)
        if registration.member_id != member.id:
            raise HTTPException(status_code=403, detail="Cannot cancel another member's registration")

        # Check self-cancellation rules
        error = check_self_cancellation_allowed(registration.activity, registration)
        if error:
            raise HTTPException(status_code=400, detail=error)

    try:
        cancel_registration(
            db,
            registration,
            cancelled_by_id=current_user.id,
            reason=data.reason if data else None,
        )
        db.commit()
    except RegistrationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/registrations/{registration_id}/status",
    response_model=RegistrationResponse,
)
def change_registration_status(
    registration_id: int,
    data: AdminStatusChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Change registration status (admin only)."""
    registration = (
        db.query(Registration)
        .options(
            joinedload(Registration.activity),
            joinedload(Registration.modality),
            joinedload(Registration.price),
        )
        .filter(Registration.id == registration_id)
        .first()
    )
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")

    try:
        admin_change_status(db, registration, data.status, data.admin_notes)
        db.commit()
        db.refresh(registration)
        return RegistrationResponse.model_validate(registration)
    except RegistrationError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Member self-service (must be before /members/{member_id} to avoid path conflict) ---


@router.get("/members/me/registrations")
def list_my_registrations(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List current user's registrations."""
    member = _get_member_for_user(db, current_user)

    query = (
        db.query(Registration)
        .filter(Registration.member_id == member.id)
        .options(joinedload(Registration.activity))
        .order_by(Registration.created_at.desc())
    )

    items, meta = paginate(query, page, per_page)

    return {
        "meta": meta.model_dump(),
        "items": [RegistrationResponse.model_validate(r) for r in items],
    }


# --- Admin: specific member's registrations ---


def _to_registration_with_activity(registration: Registration) -> RegistrationDetailResponse:
    activity_info = None
    if registration.activity:
        activity_info = RegistrationActivityInfo(
            id=registration.activity.id,
            name=registration.activity.name,
            slug=registration.activity.slug,
            starts_at=registration.activity.starts_at,
            ends_at=registration.activity.ends_at,
            location=registration.activity.location,
        )

    return RegistrationDetailResponse(
        id=registration.id,
        activity_id=registration.activity_id,
        member_id=registration.member_id,
        modality_id=registration.modality_id,
        price_id=registration.price_id,
        discount_code_id=registration.discount_code_id,
        status=registration.status,
        original_amount=float(registration.original_amount) if registration.original_amount is not None else None,
        discounted_amount=float(registration.discounted_amount) if registration.discounted_amount is not None else None,
        registration_data=registration.registration_data or {},
        member_notes=registration.member_notes,
        admin_notes=registration.admin_notes,
        cancelled_at=registration.cancelled_at,
        cancelled_reason=registration.cancelled_reason,
        cancelled_by_name=registration.cancelled_by_name,
        created_at=registration.created_at,
        activity=activity_info,
    )


@router.get("/members/{member_id}/registrations")
def list_member_registrations(
    member_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all registrations for a specific member (admin only)."""
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    query = (
        db.query(Registration)
        .filter(Registration.member_id == member_id)
        .options(joinedload(Registration.activity))
        .order_by(Registration.created_at.desc())
    )
    if status_filter:
        query = query.filter(Registration.status == status_filter)

    items, meta = paginate(query, page, per_page)

    return {
        "meta": meta.model_dump(),
        "items": [_to_registration_with_activity(r) for r in items],
    }
