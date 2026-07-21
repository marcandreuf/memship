"""Custom profile field service — definitions CRUD, access rules, value coercion.

Access is resolved in exactly one place (``can_read``/``can_write``) so the
endpoints, the value writer and the tests all agree on the matrix:

| role              | read                   | write                          |
|-------------------|------------------------|--------------------------------|
| super_admin       | always                 | always                         |
| admin, restricted | always                 | ``admin_access == "write"``    |
| member (own)      | ``member_access != hidden`` | ``member_access == "write"`` |
| member (other)    | never                  | never                          |

Following the house convention, nothing here commits — the endpoint does.
"""

from decimal import Decimal, InvalidOperation
from datetime import date

from sqlalchemy.orm import Session

from app.domains.custom_fields.models import CustomFieldDefinition, CustomFieldValue
from app.domains.custom_fields.schemas import (
    CustomFieldDefinitionCreate,
    CustomFieldDefinitionUpdate,
    CustomFieldOption,
    _check_options,
)
from app.domains.shared.enums import (
    CustomFieldAdminAccess,
    CustomFieldMemberAccess,
    CustomFieldType,
    UserRole,
)

# Length caps for the free-text types, mirrored by the frontend Zod schema.
TEXT_MAX_LENGTH = 255
TEXTAREA_MAX_LENGTH = 5000

STAFF_ROLES = {UserRole.ADMIN, UserRole.RESTRICTED}


class CustomFieldError(Exception):
    """Base class for custom-field domain errors."""


class DuplicateFieldKey(CustomFieldError):
    """A definition already exists with this key."""


class InvalidFieldValue(CustomFieldError):
    """A submitted value doesn't fit its definition."""

    def __init__(self, key: str, message: str):
        self.key = key
        self.message = message
        super().__init__(f"{key}: {message}")


class FieldNotWritable(CustomFieldError):
    """The actor may not write this field."""

    def __init__(self, key: str):
        self.key = key
        super().__init__(key)


# --- Access ---------------------------------------------------------------


def can_read(definition: CustomFieldDefinition, *, role: str, is_own: bool) -> bool:
    if role == UserRole.SUPER_ADMIN:
        return True
    if role in STAFF_ROLES:
        return True
    if role == UserRole.MEMBER and is_own:
        return definition.member_access != CustomFieldMemberAccess.HIDDEN
    return False


def can_write(definition: CustomFieldDefinition, *, role: str, is_own: bool) -> bool:
    if role == UserRole.SUPER_ADMIN:
        return True
    if role in STAFF_ROLES:
        return definition.admin_access == CustomFieldAdminAccess.WRITE
    if role == UserRole.MEMBER and is_own:
        return definition.member_access == CustomFieldMemberAccess.WRITE
    return False


def visible_definitions(
    db: Session, *, role: str, is_own: bool, include_inactive: bool = False
) -> list[CustomFieldDefinition]:
    """Definitions the actor may see, in display order."""
    return [
        d
        for d in list_definitions(db, include_inactive=include_inactive)
        if can_read(d, role=role, is_own=is_own)
    ]


# --- Value coercion -------------------------------------------------------


def validate_value(definition: CustomFieldDefinition, raw) -> str | None:
    """Coerce a submitted value to its canonical string form.

    Returns ``None`` for a cleared field. Raises ``InvalidFieldValue`` otherwise.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = raw.strip()
        if raw == "":
            return None

    field_type = definition.field_type

    if field_type == CustomFieldType.BOOLEAN:
        if isinstance(raw, bool):
            return "true" if raw else "false"
        if str(raw).lower() in {"true", "false"}:
            return str(raw).lower()
        raise InvalidFieldValue(definition.key, "Must be true or false")

    if field_type == CustomFieldType.NUMBER:
        try:
            Decimal(str(raw))
        except (InvalidOperation, ValueError):
            raise InvalidFieldValue(definition.key, "Must be a number")
        return str(raw)

    if field_type == CustomFieldType.DATE:
        try:
            return date.fromisoformat(str(raw)).isoformat()
        except ValueError:
            raise InvalidFieldValue(definition.key, "Must be a date (YYYY-MM-DD)")

    if field_type == CustomFieldType.SELECT:
        allowed = {o.get("value") for o in (definition.options or [])}
        value = str(raw)
        if value not in allowed:
            raise InvalidFieldValue(definition.key, "Not an allowed option")
        return value

    value = str(raw)
    cap = (
        TEXTAREA_MAX_LENGTH
        if field_type == CustomFieldType.TEXTAREA
        else TEXT_MAX_LENGTH
    )
    if len(value) > cap:
        raise InvalidFieldValue(definition.key, f"Must be at most {cap} characters")
    return value


# --- Definitions CRUD -----------------------------------------------------


def list_definitions(
    db: Session, *, include_inactive: bool = False
) -> list[CustomFieldDefinition]:
    query = db.query(CustomFieldDefinition)
    if not include_inactive:
        query = query.filter(CustomFieldDefinition.active.is_(True))
    return query.order_by(
        CustomFieldDefinition.sort_order, CustomFieldDefinition.id
    ).all()


def get_definition(db: Session, definition_id: int) -> CustomFieldDefinition | None:
    return (
        db.query(CustomFieldDefinition)
        .filter(CustomFieldDefinition.id == definition_id)
        .first()
    )


def get_definition_by_key(db: Session, key: str) -> CustomFieldDefinition | None:
    return (
        db.query(CustomFieldDefinition).filter(CustomFieldDefinition.key == key).first()
    )


def _dump_options(options: list[CustomFieldOption] | None) -> list[dict] | None:
    return [o.model_dump() for o in options] if options is not None else None


def create_definition(
    db: Session, data: CustomFieldDefinitionCreate
) -> CustomFieldDefinition:
    if get_definition_by_key(db, data.key):
        raise DuplicateFieldKey(data.key)

    definition = CustomFieldDefinition(
        key=data.key,
        field_type=data.field_type,
        label=data.label,
        labels=data.labels,
        help_text=data.help_text,
        options=_dump_options(data.options),
        required=data.required,
        member_access=data.member_access,
        admin_access=data.admin_access,
        sort_order=data.sort_order,
        active=data.active,
    )
    db.add(definition)
    return definition


def update_definition(
    db: Session,
    definition: CustomFieldDefinition,
    data: CustomFieldDefinitionUpdate,
) -> CustomFieldDefinition:
    payload = data.model_dump(exclude_unset=True)

    if "options" in payload:
        # Options must still fit the (immutable) field_type of this definition.
        _check_options(definition.field_type, data.options)
        payload["options"] = _dump_options(data.options)

    for key, value in payload.items():
        setattr(definition, key, value)
    return definition


def has_values(db: Session, definition: CustomFieldDefinition) -> bool:
    return (
        db.query(CustomFieldValue.id)
        .filter(CustomFieldValue.definition_id == definition.id)
        .first()
        is not None
    )


def delete_definition(db: Session, definition: CustomFieldDefinition) -> bool:
    """Hard-delete an unused definition, otherwise archive it.

    Returns True when the row was deleted, False when it was archived — the
    collected values are never discarded silently.
    """
    if has_values(db, definition):
        definition.active = False
        return False
    db.delete(definition)
    return True
