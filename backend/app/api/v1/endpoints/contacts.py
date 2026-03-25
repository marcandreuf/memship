"""Contact management endpoints for persons."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.authorization import require_admin
from app.core.security.dependencies import get_current_user
from app.db.session import get_db
from app.domains.auth.models import User
from app.domains.persons.contact_schemas import (
    ContactCreate,
    ContactResponse,
    ContactUpdate,
)
from app.domains.persons.models import Contact, ContactType, Person

router = APIRouter(prefix="/persons/{person_id}/contacts", tags=["contacts"])
detail_router = APIRouter(prefix="/contacts", tags=["contacts"])


def _contact_to_response(contact: Contact) -> dict:
    """Convert a Contact model to response dict with type name."""
    return {
        "id": contact.id,
        "contact_type_id": contact.contact_type_id,
        "contact_type_name": contact.contact_type.name if contact.contact_type else None,
        "value": contact.value,
        "label": contact.label,
        "is_primary": contact.is_primary,
    }


@router.get("/", response_model=list[ContactResponse])
def list_contacts(
    person_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all contacts for a person."""
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    contacts = (
        db.query(Contact)
        .filter(
            Contact.entity_type == "person",
            Contact.entity_id == person_id,
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
    current_user: User = Depends(require_admin),
):
    """Add a contact to a person."""
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    if data.contact_type_id:
        ct = db.query(ContactType).filter(ContactType.id == data.contact_type_id).first()
        if not ct:
            raise HTTPException(status_code=400, detail="Invalid contact type")

    contact = Contact(
        entity_type="person",
        entity_id=person_id,
        contact_type_id=data.contact_type_id,
        value=data.value,
        label=data.label,
        is_primary=data.is_primary,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return _contact_to_response(contact)


@detail_router.put("/{contact_id}", response_model=ContactResponse)
def update_contact(
    contact_id: int,
    data: ContactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update a contact."""
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

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
    current_user: User = Depends(require_admin),
):
    """Delete a contact."""
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    db.delete(contact)
    db.commit()
