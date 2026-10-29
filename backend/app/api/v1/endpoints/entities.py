"""Entity (non-person party) management endpoints.

Entities are the parties the club deals with that are not people: companies,
public bodies, foundations, other associations — typically donors. They live
on the ``party`` table directly (kind != 'person', no subtype row), which is
what lets a receipt or a mandate be addressed to one without inventing a
member. The club's own party is excluded everywhere here: it is managed from
organization settings, not as an entity.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.authorization import require_any_permission, require_permission
from app.core.pagination import paginate
from app.db.session import get_db
from app.domains.auth.models import User
from app.domains.billing.models import Receipt, SepaMandate
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.entity_schemas import (
    EntityAddressResponse,
    EntityAddressUpdate,
    EntityCreate,
    EntityResponse,
    EntityUpdate,
    PartySearchResult,
)
from app.domains.persons.models import Address, Party, PartyKind

router = APIRouter(prefix="/entities", tags=["entities"])
parties_router = APIRouter(prefix="/parties", tags=["entities"])


def _club_party_id(db: Session) -> int | None:
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    return org.party_id if org else None


def _get_entity_or_404(db: Session, entity_id: int) -> Party:
    party = (
        db.query(Party)
        .filter(Party.id == entity_id, Party.kind != "person")
        .first()
    )
    if not party or party.id == _club_party_id(db):
        raise HTTPException(status_code=404, detail="Entity not found")
    return party


def _validate_kind(db: Session, kind: str) -> None:
    valid = (
        db.query(PartyKind)
        .filter(PartyKind.code == kind, PartyKind.is_natural.is_(False))
        .first()
    )
    if not valid:
        raise HTTPException(status_code=400, detail="Invalid entity kind")


def _entity_to_dict(party: Party) -> dict:
    return {
        "id": party.id,
        "kind": party.kind,
        "name": party.display_name,
        "national_id": party.national_id,
        "email": party.email,
        "created_at": party.created_at,
    }


@router.get("/", response_model=dict)
def list_entities(
    search: str | None = None,
    kind: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("entities.read")),
):
    """List entities with optional search and kind filter."""
    query = db.query(Party).filter(Party.kind != "person")
    club_party_id = _club_party_id(db)
    if club_party_id is not None:
        query = query.filter(Party.id != club_party_id)
    if kind:
        query = query.filter(Party.kind == kind)
    if search:
        like = f"%{search}%"
        query = query.filter(
            Party.display_name.ilike(like)
            | Party.national_id.ilike(like)
            | Party.email.ilike(like)
        )

    query = query.order_by(Party.display_name, Party.id)
    items, meta = paginate(query, page, per_page)

    return {
        "items": [_entity_to_dict(p) for p in items],
        "meta": meta.model_dump(),
        "total": meta.total,
    }


@router.get("/kinds", response_model=list[dict])
def list_entity_kinds(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("entities.read")),
):
    """List the kinds an entity can have (every non-natural party kind)."""
    kinds = (
        db.query(PartyKind)
        .filter(PartyKind.is_natural.is_(False))
        .order_by(PartyKind.display_order)
        .all()
    )
    return [{"code": k.code, "name": k.name} for k in kinds]


@router.get("/{entity_id}", response_model=EntityResponse)
def get_entity(
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("entities.read")),
):
    """Get an entity by ID."""
    return _entity_to_dict(_get_entity_or_404(db, entity_id))


@router.post("/", response_model=EntityResponse, status_code=status.HTTP_201_CREATED)
def create_entity(
    data: EntityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("entities.write")),
):
    """Register a new entity."""
    _validate_kind(db, data.kind)
    party = Party(
        kind=data.kind,
        display_name=data.name,
        national_id=data.national_id,
        email=data.email,
    )
    db.add(party)
    db.commit()
    db.refresh(party)
    return _entity_to_dict(party)


@router.put("/{entity_id}", response_model=EntityResponse)
def update_entity(
    entity_id: int,
    data: EntityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("entities.write")),
):
    """Update an entity's own fields."""
    party = _get_entity_or_404(db, entity_id)
    update_data = data.model_dump(exclude_unset=True)
    if "kind" in update_data:
        _validate_kind(db, update_data["kind"])
    if "name" in update_data:
        party.display_name = update_data.pop("name")
    for key, value in update_data.items():
        setattr(party, key, value)
    db.commit()
    db.refresh(party)
    return _entity_to_dict(party)


@router.delete("/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entity(
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("entities.write")),
):
    """Delete an entity, refusing while financial history references it.

    Receipts and mandates FK ``party`` with RESTRICT, so the database would
    refuse anyway; checking first turns a 500 into a 409 that says why.
    Contacts and addresses cascade with the party.
    """
    party = _get_entity_or_404(db, entity_id)
    receipts = db.query(Receipt).filter(Receipt.party_id == party.id).count()
    mandates = db.query(SepaMandate).filter(SepaMandate.party_id == party.id).count()
    if receipts or mandates:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "entity_has_history",
                "receipts": receipts,
                "mandates": mandates,
            },
        )
    db.delete(party)
    db.commit()


@router.get("/{entity_id}/address", response_model=EntityAddressResponse | None)
def get_entity_address(
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("entities.read")),
):
    """Get the entity's address — one primary address, like the club's."""
    party = _get_entity_or_404(db, entity_id)
    return (
        db.query(Address)
        .filter(Address.party_id == party.id, Address.is_active.is_(True))
        .first()
    )


@router.put("/{entity_id}/address", response_model=EntityAddressResponse)
def update_entity_address(
    entity_id: int,
    data: EntityAddressUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("entities.write")),
):
    """Create or update the entity's single primary address."""
    party = _get_entity_or_404(db, entity_id)
    address = db.query(Address).filter(Address.party_id == party.id).first()

    if address:
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(address, key, value)
    else:
        address = Address(party_id=party.id, is_primary=True, **data.model_dump())
        db.add(address)

    db.commit()
    db.refresh(address)
    return address


@parties_router.get("/search", response_model=list[PartySearchResult])
def search_parties(
    q: str = Query(..., min_length=1, max_length=255),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_any_permission("members.read", "entities.read", "billing.read")
    ),
):
    """Search every party — persons and entities alike — for the pickers.

    Feeds the fields that address something to a party (a mandate, a receipt),
    which is why ``billing.read`` grants it without either people permission.
    The club's own party is excluded: nothing gets addressed to oneself.
    """
    like = f"%{q}%"
    query = db.query(Party).filter(
        Party.display_name.ilike(like)
        | Party.national_id.ilike(like)
        | Party.email.ilike(like)
    )
    club_party_id = _club_party_id(db)
    if club_party_id is not None:
        query = query.filter(Party.id != club_party_id)
    parties = query.order_by(Party.display_name, Party.id).limit(10).all()
    return [
        {
            "id": p.id,
            "display_name": p.display_name,
            "kind": p.kind,
            "national_id": p.national_id,
        }
        for p in parties
    ]
