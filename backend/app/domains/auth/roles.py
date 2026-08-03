"""Role assignment, authoring and the escalation guard."""

import re

from sqlalchemy.orm import Session

from app.core.authorization import resolve_permissions
from app.core.permissions import (
    ALL_KEYS,
    MEMBER_SLUG,
    RESERVED_KEYS,
    SUPER_ADMIN_SLUG,
)
from app.domains.audit.models import AuditLog
from app.domains.auth.models import Role, RolePermission, User, UserRoleAssignment


class RoleError(Exception):
    pass


class SlugTaken(RoleError):
    def __init__(self, slug: str, name: str):
        self.slug, self.name = slug, name
        super().__init__(slug)


class UnknownPermissions(RoleError):
    def __init__(self, keys: set[str]):
        self.keys = keys
        super().__init__(", ".join(sorted(keys)))


class ReservedPermissions(RoleError):
    def __init__(self, keys: set[str]):
        self.keys = keys
        super().__init__(", ".join(sorted(keys)))


class RoleInUse(RoleError):
    def __init__(self, count: int):
        self.count = count
        super().__init__(str(count))


class SystemRoleLocked(RoleError):
    pass


class EscalationBlocked(RoleError):
    def __init__(self, keys: set[str]):
        self.keys = keys
        super().__init__(", ".join(sorted(keys)))


class RolesRequired(RoleError):
    pass


class LastSuperAdmin(RoleError):
    pass


def assign_roles(db: Session, user: User, *extra_slugs: str) -> None:
    """Attach ``member`` — which every account holds permanently — plus any
    staff role named by slug."""
    slugs = {MEMBER_SLUG, *extra_slugs}
    roles = db.query(Role).filter(Role.slug.in_(slugs)).all()

    already = {a.role_id for a in user.role_assignments}
    for role in roles:
        if role.id not in already:
            db.add(UserRoleAssignment(user_id=user.id, role_id=role.id))


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")[:50]


def validate_keys(keys: set[str], *, is_system: bool) -> None:
    unknown = keys - ALL_KEYS
    if unknown:
        raise UnknownPermissions(unknown)
    reserved = keys & RESERVED_KEYS
    if reserved and not is_system:
        raise ReservedPermissions(reserved)


def assigned_user_count(db: Session, role_id: int) -> int:
    return (
        db.query(UserRoleAssignment).filter(UserRoleAssignment.role_id == role_id).count()
    )


def role_permission_keys(role: Role) -> frozenset[str]:
    """What holding this role grants. ``super_admin`` stores no rows, so it must
    be answered from the catalog — see ``resolve_permissions``."""
    if role.slug == SUPER_ADMIN_SLUG:
        return ALL_KEYS
    return frozenset(role.permission_keys & ALL_KEYS)


def is_assignable_by(role: Role, caller: User) -> bool:
    if role.slug == SUPER_ADMIN_SLUG:
        return any(r.slug == SUPER_ADMIN_SLUG for r in caller.roles)
    return role_permission_keys(role) <= resolve_permissions(caller)


def _audit(
    db: Session, *, table: str, record_id: int, action: str, actor: User, fields: list[str]
) -> None:
    db.add(
        AuditLog(
            table_name=table,
            record_id=record_id,
            action=action,
            user_id=actor.id,
            changed_fields=fields,
        )
    )


def create_role(
    db: Session, *, name: str, description: str | None, keys: set[str], actor: User
) -> Role:
    validate_keys(keys, is_system=False)
    slug = slugify(name)
    clash = db.query(Role).filter(Role.slug == slug).first()
    if clash is not None:
        raise SlugTaken(slug, clash.name)

    role = Role(slug=slug, name=name.strip(), description=description, is_system=False)
    role.permissions = [RolePermission(permission_key=k) for k in sorted(keys)]
    db.add(role)
    db.flush()
    _audit(
        db,
        table="roles",
        record_id=role.id,
        action="create",
        actor=actor,
        fields=[f"+{k}" for k in sorted(keys)],
    )
    return role


def update_role(
    db: Session,
    role: Role,
    *,
    name: str | None,
    description: str | None,
    keys: set[str] | None,
    actor: User,
) -> Role:
    if role.slug == SUPER_ADMIN_SLUG:
        raise SystemRoleLocked()

    changed: list[str] = []

    if keys is not None:
        validate_keys(keys, is_system=role.is_system)
        before = role.permission_keys
        changed += [f"+{k}" for k in sorted(keys - before)]
        changed += [f"-{k}" for k in sorted(before - keys)]
        role.permissions = [RolePermission(permission_key=k) for k in sorted(keys)]

    # A system role's name and slug are fixed; only its permission set is tunable.
    if not role.is_system:
        if name is not None and name.strip() != role.name:
            role.name = name.strip()
            changed.append("name")
        if description is not None and description != role.description:
            role.description = description
            changed.append("description")

    db.flush()
    if changed:
        _audit(
            db,
            table="roles",
            record_id=role.id,
            action="update",
            actor=actor,
            fields=changed,
        )
    return role


def delete_role(db: Session, role: Role, *, actor: User) -> None:
    if role.is_system:
        raise SystemRoleLocked()
    count = assigned_user_count(db, role.id)
    if count:
        raise RoleInUse(count)
    role_id, slug = role.id, role.slug
    db.delete(role)
    db.flush()
    _audit(
        db, table="roles", record_id=role_id, action="delete", actor=actor, fields=[slug]
    )


def replace_user_roles(db: Session, user: User, role_ids: list[int], *, caller: User) -> None:
    if not role_ids:
        raise RolesRequired()

    roles = db.query(Role).filter(Role.id.in_(set(role_ids))).all()
    if len(roles) != len(set(role_ids)):
        raise UnknownPermissions(set())

    # The super_admin role is assignable only by a super admin. Stated as a rule
    # rather than derived from the subset check below, which it would pass
    # trivially: super_admin stores no permission rows.
    if any(r.slug == SUPER_ADMIN_SLUG for r in roles) and not any(
        r.slug == SUPER_ADMIN_SLUG for r in caller.roles
    ):
        raise EscalationBlocked(set())

    granted: set[str] = set()
    for role in roles:
        granted |= role_permission_keys(role)
    held = resolve_permissions(caller)
    if not granted <= held:
        raise EscalationBlocked(granted - held)

    losing_super = any(
        r.slug == SUPER_ADMIN_SLUG for r in user.roles
    ) and not any(r.slug == SUPER_ADMIN_SLUG for r in roles)
    if losing_super and _super_admin_count(db) <= 1:
        raise LastSuperAdmin()

    member_role = db.query(Role).filter(Role.slug == MEMBER_SLUG).one()
    keep = {r.id for r in roles} | {member_role.id}

    before = {r.slug: r.id for r in user.roles}
    by_id = {r.id: r for r in db.query(Role).filter(Role.id.in_(keep)).all()}

    db.query(UserRoleAssignment).filter(UserRoleAssignment.user_id == user.id).delete()
    db.flush()
    for role_id in sorted(keep):
        db.add(UserRoleAssignment(user_id=user.id, role_id=role_id, assigned_by=caller.id))
    db.flush()

    after = {r.slug for r in by_id.values()}
    changed = [f"+{s}" for s in sorted(after - set(before))]
    changed += [f"-{s}" for s in sorted(set(before) - after)]
    if changed:
        _audit(
            db,
            table="user_roles",
            record_id=user.id,
            action="update",
            actor=caller,
            fields=changed,
        )


def _super_admin_count(db: Session) -> int:
    return (
        db.query(UserRoleAssignment)
        .join(Role, Role.id == UserRoleAssignment.role_id)
        .filter(Role.slug == SUPER_ADMIN_SLUG)
        .count()
    )
