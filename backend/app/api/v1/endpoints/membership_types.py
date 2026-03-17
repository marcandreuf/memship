"""Membership type endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.authorization import require_admin
from app.core.db_utils import get_or_404
from app.core.security.dependencies import get_current_user
from app.db.session import get_db
from app.domains.auth.models import User
from app.domains.members.models import MembershipType
from app.domains.members.schemas import (
    MembershipTypeCreate,
    MembershipTypeResponse,
    MembershipTypeUpdate,
)

router = APIRouter(prefix="/membership-types", tags=["membership-types"])


def _to_response(mt: MembershipType) -> MembershipTypeResponse:
    return MembershipTypeResponse(
        id=mt.id,
        name=mt.name,
        slug=mt.slug,
        description=mt.description,
        group_id=mt.group_id,
        group_name=mt.group.name if mt.group else None,
        base_price=mt.base_price,
        billing_frequency=mt.billing_frequency,
        is_active=mt.is_active,
        created_at=mt.created_at,
    )


@router.get("/", response_model=list[MembershipTypeResponse])
def list_membership_types(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    types = (
        db.query(MembershipType)
        .options(joinedload(MembershipType.group))
        .order_by(MembershipType.display_order)
        .all()
    )
    return [_to_response(mt) for mt in types]


@router.get("/{type_id}", response_model=MembershipTypeResponse)
def get_membership_type(
    type_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mt = (
        db.query(MembershipType)
        .options(joinedload(MembershipType.group))
        .filter(MembershipType.id == type_id)
        .first()
    )
    if not mt:
        raise HTTPException(status_code=404, detail="MembershipType not found")
    return _to_response(mt)


@router.post("/", response_model=MembershipTypeResponse, status_code=status.HTTP_201_CREATED)
def create_membership_type(
    data: MembershipTypeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    existing = db.query(MembershipType).filter(MembershipType.slug == data.slug).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Membership type with slug '{data.slug}' already exists",
        )

    mt = MembershipType(**data.model_dump())
    db.add(mt)
    db.commit()
    db.refresh(mt)
    return _to_response(mt)


@router.put("/{type_id}", response_model=MembershipTypeResponse)
def update_membership_type(
    type_id: int,
    data: MembershipTypeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    mt = get_or_404(db, MembershipType, type_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(mt, key, value)
    db.commit()
    db.refresh(mt)
    return _to_response(mt)


@router.delete("/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_membership_type(
    type_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    mt = get_or_404(db, MembershipType, type_id)
    mt.is_active = False
    db.commit()
