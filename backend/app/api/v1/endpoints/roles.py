"""Role authoring and assignment."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.authorization import require_permission
from app.core.db_utils import get_or_404
from app.core.permissions import CATALOG
from app.db.session import get_db
from app.domains.auth import roles as role_service
from app.domains.auth.models import Role, User
from app.domains.auth.schemas import (
    PermissionRead,
    RoleCreate,
    RoleRead,
    RoleSummary,
    RoleUpdate,
    UserActiveUpdate,
    UserListItem,
    UserRolesUpdate,
)
from app.domains.organizations.models import OrganizationSettings

router = APIRouter(prefix="/roles", tags=["roles"])
permissions_router = APIRouter(prefix="/permissions", tags=["roles"])
users_router = APIRouter(prefix="/users", tags=["users"])


def require_custom_roles_enabled(db: Session) -> None:
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    features = (org.features or {}) if org else {}
    if not features.get("custom_roles"):
        raise HTTPException(status_code=404, detail="Not found")


def _to_read(db: Session, role: Role, caller: User) -> RoleRead:
    return RoleRead(
        id=role.id,
        slug=role.slug,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permission_keys=sorted(role_service.role_permission_keys(role)),
        assigned_user_count=role_service.assigned_user_count(db, role.id),
        assignable=role_service.is_assignable_by(role, caller),
    )


@permissions_router.get("", response_model=list[PermissionRead])
def list_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles.read")),
):
    require_custom_roles_enabled(db)
    return [
        PermissionRead(
            key=p.key,
            domain=p.domain,
            action=p.action,
            reserved=p.reserved,
            label_key=p.label_key,
            description_key=p.description_key,
        )
        for p in CATALOG
    ]


@router.get("", response_model=list[RoleRead])
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles.read")),
):
    require_custom_roles_enabled(db)
    roles = db.query(Role).order_by(Role.is_system.desc(), Role.name).all()
    return [_to_read(db, r, current_user) for r in roles]


@router.get("/{role_id}", response_model=RoleRead)
def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles.read")),
):
    require_custom_roles_enabled(db)
    return _to_read(db, get_or_404(db, Role, role_id), current_user)


@router.post("", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
def create_role(
    data: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles.write")),
):
    require_custom_roles_enabled(db)
    try:
        role = role_service.create_role(
            db, name=data.name, description=data.description,
            keys=set(data.permission_keys), actor=current_user
        )
    except role_service.SlugTaken as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "role_slug_exists", "slug": exc.slug, "name": exc.name},
        )
    except role_service.UnknownPermissions as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "unknown_permissions", "keys": sorted(exc.keys)},
        )
    except role_service.ReservedPermissions as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "reserved_permissions", "keys": sorted(exc.keys)},
        )
    db.commit()
    return _to_read(db, role, current_user)


@router.put("/{role_id}", response_model=RoleRead)
def update_role(
    role_id: int,
    data: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles.write")),
):
    require_custom_roles_enabled(db)
    role = get_or_404(db, Role, role_id)
    try:
        role_service.update_role(
            db,
            role,
            name=data.name,
            description=data.description,
            keys=None if data.permission_keys is None else set(data.permission_keys),
            actor=current_user,
        )
    except role_service.SystemRoleLocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail={"code": "role_locked"}
        )
    except role_service.UnknownPermissions as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "unknown_permissions", "keys": sorted(exc.keys)},
        )
    except role_service.ReservedPermissions as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "reserved_permissions", "keys": sorted(exc.keys)},
        )
    db.commit()
    return _to_read(db, role, current_user)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles.write")),
):
    require_custom_roles_enabled(db)
    role = get_or_404(db, Role, role_id)
    try:
        role_service.delete_role(db, role, actor=current_user)
    except role_service.SystemRoleLocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail={"code": "role_locked"}
        )
    except role_service.RoleInUse as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "role_in_use", "assigned_user_count": exc.count},
        )
    db.commit()


@users_router.get("", response_model=list[UserListItem])
def list_users(
    q: str | None = Query(default=None),
    role_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.read")),
):
    require_custom_roles_enabled(db)
    query = db.query(User)
    if role_id is not None:
        query = query.filter(User.roles.any(Role.id == role_id))
    if q:
        query = query.filter(User.email.ilike(f"%{q}%"))
    return [_user_item(u) for u in query.order_by(User.email).all()]


@users_router.get("/{user_id}", response_model=UserListItem)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.read")),
):
    require_custom_roles_enabled(db)
    return _user_item(get_or_404(db, User, user_id))


@users_router.put("/{user_id}/roles", response_model=UserListItem)
def replace_user_roles(
    user_id: int,
    data: UserRolesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.write")),
):
    require_custom_roles_enabled(db)
    user = get_or_404(db, User, user_id)
    try:
        role_service.replace_user_roles(db, user, data.role_ids, caller=current_user)
    except role_service.RolesRequired:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "roles_required"}
        )
    except role_service.EscalationBlocked as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "escalation_blocked", "keys": sorted(exc.keys)},
        )
    except role_service.LastSuperAdmin:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail={"code": "last_super_admin"}
        )
    db.commit()
    db.refresh(user)
    return _user_item(user)


@users_router.put("/{user_id}/active", response_model=UserListItem)
def set_user_active(
    user_id: int,
    data: UserActiveUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.write")),
):
    require_custom_roles_enabled(db)
    user = get_or_404(db, User, user_id)
    user.is_active = data.is_active
    db.commit()
    db.refresh(user)
    return _user_item(user)


def _user_item(user: User) -> UserListItem:
    return UserListItem(
        id=user.id,
        email=user.email,
        first_name=user.person.first_name if user.person else "",
        last_name=user.person.last_name if user.person else "",
        is_active=bool(user.is_active),
        roles=[RoleSummary(id=r.id, slug=r.slug, name=r.name) for r in user.roles],
    )
