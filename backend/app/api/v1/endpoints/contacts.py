"""Contact management endpoints for persons and entities."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.authorization import require_any_permission, require_permission, user_has
from app.core.security.dependencies import get_current_user
from app.db.session import get_db
from app.domains.auth.models import User
from app.domains.persons.contact_schemas import (
    ContactCreate,
    ContactResponse,
    ContactUpdate,
)
from app.domains.persons.models import Contact, ContactType, Party, Person

router = APIRouter(prefix="/persons/{person_id}/contacts", tags=["contacts"])
# Entity contacts: same table, same handlers' logic, scoped by party. Person
# parties 404 here — people keep the /persons routes and their self-service
# rules, so this router only ever needs the entities permissions.
party_router = APIRouter(prefix="/parties/{party_id}/contacts", tags=["contacts"])
detail_router = APIRouter(prefix="/contacts", tags=["contacts"])
types_router = APIRouter(prefix="/contact-types", tags=["contacts"])


@types_router.get("/")
def list_contact_types(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("members.read", "self.activities.read")),
):
    """List all active contact types."""
    types = (
        db.query(ContactType)
        .filter(ContactType.is_active.is_(True))
        .order_by(ContactType.display_order)
        .all()
    )
    # ``channel`` is what groups types into one primary slot and one cap:
    # phone_home and phone_mobile are both ``phone``. Without it the client
    # would have to guess the grouping from the code prefix, which the
    # people-cluster migration only does as a one-time backfill with an
    # ``other`` fallback for codes it cannot read.
    return [
        {"id": ct.id, "code": ct.code, "name": ct.name, "channel": ct.channel}
        for ct in types
    ]


def _contact_to_response(contact: Contact) -> dict:
    """Convert a Contact model to response dict with type name."""
    return {
        "id": contact.id,
        "contact_type_id": contact.contact_type_id,
        "contact_type_name": contact.contact_type.name if contact.contact_type else None,
        "channel": contact.channel,
        "value": contact.value,
        "label": contact.label,
        "is_primary": contact.is_primary,
    }


@router.get("/", response_model=list[ContactResponse])
def list_contacts(
    person_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("members.read", "self.profile.read")),
):
    """List all contacts for a person."""
    person = db.query(Person).filter(Person.party_id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    contacts = (
        db.query(Contact)
        .filter(
            Contact.party_id == person.party_id,
            Contact.is_active.is_(True),
        )
        .order_by(Contact.display_order, Contact.id)
        .all()
    )
    return [_contact_to_response(c) for c in contacts]


@router.post("/", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
def create_contact(
    person_id: int,
    data: ContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("members.write")),
):
    """Add a contact to a person."""
    person = db.query(Person).filter(Person.party_id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    if data.contact_type_id:
        ct = db.query(ContactType).filter(ContactType.id == data.contact_type_id).first()
        if not ct:
            raise HTTPException(status_code=400, detail="Invalid contact type")

    contact = Contact(
        party_id=person.party_id,
        contact_type_id=data.contact_type_id,
        value=data.value,
        label=data.label,
        is_primary=data.is_primary,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return _contact_to_response(contact)


def _get_entity_party_or_404(db: Session, party_id: int) -> Party:
    party = db.query(Party).filter(
        Party.id == party_id, Party.kind != "person"
    ).first()
    if not party:
        raise HTTPException(status_code=404, detail="Entity not found")
    return party


@party_router.get("/", response_model=list[ContactResponse])
def list_entity_contacts(
    party_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("entities.read")),
):
    """List all contacts for an entity."""
    party = _get_entity_party_or_404(db, party_id)
    contacts = (
        db.query(Contact)
        .filter(Contact.party_id == party.id, Contact.is_active.is_(True))
        .order_by(Contact.display_order, Contact.id)
        .all()
    )
    return [_contact_to_response(c) for c in contacts]


@party_router.post("/", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
def create_entity_contact(
    party_id: int,
    data: ContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("entities.write")),
):
    """Add a contact to an entity."""
    party = _get_entity_party_or_404(db, party_id)

    if data.contact_type_id:
        ct = db.query(ContactType).filter(ContactType.id == data.contact_type_id).first()
        if not ct:
            raise HTTPException(status_code=400, detail="Invalid contact type")

    contact = Contact(
        party_id=party.id,
        contact_type_id=data.contact_type_id,
        value=data.value,
        label=data.label,
        is_primary=data.is_primary,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return _contact_to_response(contact)


def _require_write_on_owner(db: Session, current_user: User, contact: Contact) -> None:
    """A contact write needs the permission matching its owner's kind: a
    person's contact is members data, an entity's is entities data."""
    kind = db.query(Party.kind).filter(Party.id == contact.party_id).scalar()
    required = "members.write" if kind == "person" else "entities.write"
    if not user_has(current_user, required):
        raise HTTPException(status_code=403, detail={"code": "forbidden", "required": required})


@detail_router.put("/{contact_id}", response_model=ContactResponse)
def update_contact(
    contact_id: int,
    data: ContactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("members.write", "entities.write")),
):
    """Update a contact."""
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    _require_write_on_owner(db, current_user, contact)

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(contact, key, value)
    db.commit()
    db.refresh(contact)
    return _contact_to_response(contact)


@detail_router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission("members.write", "entities.write")),
):
    """Delete a contact."""
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    _require_write_on_owner(db, current_user, contact)

    db.delete(contact)
    db.commit()
