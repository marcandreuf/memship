"""Billing concept endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.authorization import require_admin
from app.core.security.dependencies import get_current_user
from app.db.session import get_db
from app.domains.auth.models import User
from app.domains.billing.models import Concept
from app.domains.billing.schemas import ConceptCreate, ConceptResponse, ConceptUpdate

router = APIRouter(prefix="/concepts", tags=["concepts"])


@router.get("/", response_model=list[ConceptResponse])
def list_concepts(
    concept_type: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all active billing concepts."""
    query = db.query(Concept).filter(Concept.is_active.is_(True))
    if concept_type:
        query = query.filter(Concept.concept_type == concept_type)
    return query.order_by(Concept.concept_type, Concept.name).all()


@router.post("/", response_model=ConceptResponse, status_code=status.HTTP_201_CREATED)
def create_concept(
    data: ConceptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a billing concept."""
    if data.code:
        existing = db.query(Concept).filter(Concept.code == data.code).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Concept with code '{data.code}' already exists",
            )

    concept = Concept(**data.model_dump(exclude_unset=True))
    db.add(concept)
    db.commit()
    db.refresh(concept)
    return concept


@router.put("/{concept_id}", response_model=ConceptResponse)
def update_concept(
    concept_id: int,
    data: ConceptUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update a billing concept."""
    concept = db.query(Concept).filter(Concept.id == concept_id).first()
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(concept, key, value)
    db.commit()
    db.refresh(concept)
    return concept
