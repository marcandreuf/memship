"""Membership type endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

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


@router.get("/", response_model=list[MembershipTypeResponse])
def list_membership_types(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(MembershipType).order_by(MembershipType.display_order).all()


@router.get("/{type_id}", response_model=MembershipTypeResponse)
def get_membership_type(
    type_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_or_404(db, MembershipType, type_id)


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
    return mt


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
    return mt


@router.delete("/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_membership_type(
    type_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    mt = get_or_404(db, MembershipType, type_id)
    mt.is_active = False
    db.commit()
