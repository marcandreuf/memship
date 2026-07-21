"""Custom profile field definition endpoints.

Definitions are super-admin-only to write; any authenticated user may list them,
filtered to what their role is allowed to see, because the member's Custom
fields tab needs the definitions to render itself.

Like the member card, these return 404 rather than 403 when
``features.custom_profile_fields`` is off, so a disabled feature is invisible
rather than merely forbidden.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.authorization import require_super_admin
from app.core.security.dependencies import get_current_user
from app.db.session import get_db
from app.domains.auth.models import User
from app.domains.custom_fields.models import CustomFieldDefinition
from app.domains.custom_fields.schemas import (
    CustomFieldDefinitionCreate,
    CustomFieldDefinitionRead,
    CustomFieldDefinitionUpdate,
)
from app.domains.custom_fields.service import (
    DuplicateFieldKey,
    FieldNotWritable,
    InvalidFieldValue,
    UnknownFieldKey,
    can_write,
    create_definition,
    delete_definition,
    get_definition,
    get_person_values,
    set_person_values,
    update_definition,
    visible_definitions,
)
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person
from app.domains.shared.enums import UserRole

router = APIRouter(prefix="/custom-fields", tags=["custom-fields"])
values_router = APIRouter(
    prefix="/persons/{person_id}/custom-fields", tags=["custom-fields"]
)
me_router = APIRouter(prefix="/me/custom-fields", tags=["custom-fields"])


def require_custom_fields_enabled(db: Session) -> None:
    org = (
        db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    )
    features = (org.features or {}) if org else {}
    if not features.get("custom_profile_fields"):
        raise HTTPException(status_code=404, detail="Not found")


def to_read(
    definition: CustomFieldDefinition, *, role: str, is_own: bool
) -> CustomFieldDefinitionRead:
    out = CustomFieldDefinitionRead.model_validate(definition)
    out.writable = can_write(definition, role=role, is_own=is_own)
    return out


def _duplicate_key_error(key: str) -> HTTPException:
    """422 in the shape the frontend maps onto the offending form field."""
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=[
            {
                "loc": ["body", "key"],
                "msg": f"A field with key '{key}' already exists",
                "type": "value_error",
            }
        ],
    )


@router.get("/", response_model=list[CustomFieldDefinitionRead])
def list_custom_fields(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List definitions the current user may see, in display order."""
    require_custom_fields_enabled(db)

    # A member only ever lists definitions in order to render their own record.
    is_own = current_user.role == UserRole.MEMBER
    if include_inactive and current_user.role != UserRole.SUPER_ADMIN:
        include_inactive = False

    definitions = visible_definitions(
        db, role=current_user.role, is_own=is_own, include_inactive=include_inactive
    )
    return [
        to_read(d, role=current_user.role, is_own=is_own) for d in definitions
    ]


@router.post(
    "/", response_model=CustomFieldDefinitionRead, status_code=status.HTTP_201_CREATED
)
def create_custom_field(
    data: CustomFieldDefinitionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    require_custom_fields_enabled(db)
    try:
        definition = create_definition(db, data)
    except DuplicateFieldKey:
        raise _duplicate_key_error(data.key)
    db.commit()
    db.refresh(definition)
    return to_read(definition, role=current_user.role, is_own=False)


@router.get("/{definition_id}", response_model=CustomFieldDefinitionRead)
def get_custom_field(
    definition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    require_custom_fields_enabled(db)
    definition = get_definition(db, definition_id)
    if not definition:
        raise HTTPException(status_code=404, detail="Custom field not found")
    return to_read(definition, role=current_user.role, is_own=False)


@router.patch("/{definition_id}", response_model=CustomFieldDefinitionRead)
def update_custom_field(
    definition_id: int,
    data: CustomFieldDefinitionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Update a definition. `key` and `field_type` are immutable by design."""
    require_custom_fields_enabled(db)
    definition = get_definition(db, definition_id)
    if not definition:
        raise HTTPException(status_code=404, detail="Custom field not found")

    try:
        update_definition(db, definition, data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[{"loc": ["body", "options"], "msg": str(exc), "type": "value_error"}],
        )
    db.commit()
    db.refresh(definition)
    return to_read(definition, role=current_user.role, is_own=False)


@router.delete("/{definition_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_custom_field(
    definition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Delete an unused definition; archive it instead once it holds values."""
    require_custom_fields_enabled(db)
    definition = get_definition(db, definition_id)
    if not definition:
        raise HTTPException(status_code=404, detail="Custom field not found")

    delete_definition(db, definition)
    db.commit()


# --- Values ---------------------------------------------------------------


def _resolve_person(db: Session, person_id: int, current_user: User) -> bool:
    """404 unknown persons, 403 a member reaching past their own record.

    Returns whether the record belongs to the caller, which drives the whole
    access matrix downstream.
    """
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    is_own = current_user.person_id == person_id
    if current_user.role == UserRole.MEMBER and not is_own:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return is_own


def _own_person_id(current_user: User) -> int:
    if not current_user.person_id:
        raise HTTPException(status_code=403, detail="No person profile")
    return current_user.person_id


def _field_error(key: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=[{"loc": ["body", key], "msg": message, "type": "value_error"}],
    )


def _save_values(
    db: Session, person_id: int, submitted: dict, *, role: str, is_own: bool
) -> dict[str, str | None]:
    try:
        set_person_values(db, person_id, submitted, role=role, is_own=is_own)
    except InvalidFieldValue as exc:
        raise _field_error(exc.key, exc.message)
    except FieldNotWritable as exc:
        raise _field_error(exc.key, "This field is not editable")
    except UnknownFieldKey as exc:
        raise _field_error(exc.key, "Unknown field")
    db.commit()
    return get_person_values(db, person_id, role=role, is_own=is_own)


@me_router.get("/", response_model=dict[str, str | None])
def get_my_custom_fields(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The current user's own values — every field they may see."""
    require_custom_fields_enabled(db)
    person_id = _own_person_id(current_user)
    return get_person_values(db, person_id, role=current_user.role, is_own=True)


@me_router.put("/", response_model=dict[str, str | None])
def update_my_custom_fields(
    values: dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_custom_fields_enabled(db)
    person_id = _own_person_id(current_user)
    return _save_values(
        db, person_id, values, role=current_user.role, is_own=True
    )


@values_router.get("/", response_model=dict[str, str | None])
def get_person_custom_fields(
    person_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_custom_fields_enabled(db)
    is_own = _resolve_person(db, person_id, current_user)
    return get_person_values(db, person_id, role=current_user.role, is_own=is_own)


@values_router.put("/", response_model=dict[str, str | None])
def update_person_custom_fields(
    person_id: int,
    values: dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Replace this person's values. Fields the caller can't write are untouched."""
    require_custom_fields_enabled(db)
    is_own = _resolve_person(db, person_id, current_user)
    return _save_values(
        db, person_id, values, role=current_user.role, is_own=is_own
    )
