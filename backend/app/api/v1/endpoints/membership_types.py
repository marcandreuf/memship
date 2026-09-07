"""Membership type endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.authorization import require_permission
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
        min_age=mt.min_age,
        max_age=mt.max_age,
        is_active=mt.is_active,
        is_default=mt.is_default,
        created_at=mt.created_at,
    )


@router.get("/", response_model=list[MembershipTypeResponse])
def list_membership_types(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("self.activities.read")),
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
    current_user: User = Depends(require_permission("self.activities.read")),
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
    current_user: User = Depends(require_permission("membership.write")),
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
    current_user: User = Depends(require_permission("membership.write")),
):
    mt = get_or_404(db, MembershipType, type_id)
    update_data = data.model_dump(exclude_unset=True)

    # The database refuses a priced default and a second default outright, so
    # both rules are checked here first — an IntegrityError would reach the
    # admin as a 500 with nothing to act on.
    will_be_default = update_data.get("is_default", mt.is_default)
    will_cost = float(update_data.get("base_price", mt.base_price) or 0)
    if will_be_default and will_cost > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The tier new sign-ups land on must stay free",
        )
    if mt.is_default and update_data.get("is_default") is False:
        # Clearing it outright would leave sign-ups with no tier at all, and a
        # member with no tier is barred from every activity that restricts
        # membership types. Moving the flag to another tier is the way out.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New sign-ups need a tier — mark another one the default instead",
        )
    if update_data.get("is_default") and not mt.is_default:
        db.query(MembershipType).filter(
            MembershipType.is_default == True, MembershipType.id != mt.id
        ).update({"is_default": False}, synchronize_session=False)
        db.flush()

    for key, value in update_data.items():
        setattr(mt, key, value)
    db.commit()
    db.refresh(mt)
    return _to_response(mt)


@router.delete("/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_membership_type(
    type_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("membership.write")),
):
    mt = get_or_404(db, MembershipType, type_id)
    mt.is_active = False
    db.commit()
