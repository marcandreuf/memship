"""Person endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db_utils import get_or_404
from app.core.security.dependencies import get_current_user
from app.core.authorization import require_permission, user_has
from app.db.session import get_db
from app.domains.auth.models import User
from app.domains.members.schemas import PersonResponse
from app.domains.persons.models import Person

router = APIRouter(prefix="/persons", tags=["persons"])


@router.get("/{person_id}", response_model=PersonResponse)
def get_person(
    person_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("self.profile.read")),
):
    person = get_or_404(db, Person, person_id)

    # Members can only view their own person
    if not user_has(current_user, "members.read") and current_user.person_id != person_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    return person


@router.put("/{person_id}", response_model=PersonResponse)
def update_person(
    person_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("self.profile.write")),
):
    person = get_or_404(db, Person, person_id)

    if not user_has(current_user, "members.write") and current_user.person_id != person_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    allowed_fields = {
        "first_name", "last_name", "email", "date_of_birth", "gender", "national_id"
    }
    for key, value in data.items():
        if key in allowed_fields:
            setattr(person, key, value)

    db.commit()
    db.refresh(person)
    return person
