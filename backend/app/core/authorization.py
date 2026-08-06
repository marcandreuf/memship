"""Permission-based access control."""

import logging

from fastapi import Depends, HTTPException, Request, status

from app.core.permissions import ALL_KEYS, SELF_KEYS, SUPER_ADMIN_SLUG
from app.core.security.dependencies import get_current_user
from app.domains.auth.models import User

logger = logging.getLogger(__name__)


def resolve_permissions(user: User) -> frozenset[str]:
    """The permissions a user effectively holds.

    A super admin resolves to the *whole catalog* rather than to its stored rows,
    which are deliberately empty. Returning the empty set here would silently
    satisfy every subset check — letting an admin grant super_admin — and fail
    every "holds any permission" check. Nothing outside this function may read
    ``role_permissions`` to decide what a user can do.
    """
    if any(role.slug == SUPER_ADMIN_SLUG for role in user.roles):
        logger.debug(
            "resolve_permissions: user_id=%s roles=%s -> super admin, all permissions granted",
            user.id,
            [role.slug for role in user.roles],
        )
        return ALL_KEYS

    permissions = frozenset(
        key
        for role in user.roles
        for key in role.permission_keys
        # A key dropped from the catalog must not survive in stored rows, or a
        # downgrade would re-grant it.
        if key in ALL_KEYS
    )
    logger.debug(
        "resolve_permissions: user_id=%s roles=%s permissions=%s",
        user.id,
        [role.slug for role in user.roles],
        sorted(permissions),
    )
    return permissions


def get_permissions(request: Request, user: User) -> frozenset[str]:
    cached = getattr(request.state, "resolved_permissions", None)
    if cached is None:
        cached = resolve_permissions(user)
        request.state.resolved_permissions = cached
    return cached


def is_staff(permissions: frozenset[str]) -> bool:
    return bool(permissions - SELF_KEYS)


def _forbidden(required: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "forbidden", "required": required},
    )


def require_permission(*keys: str):
    """Dependency: the user must hold EVERY listed permission."""

    def dependency(
        request: Request, current_user: User = Depends(get_current_user)
    ) -> User:
        held = get_permissions(request, current_user)
        for key in keys:
            if key not in held:
                raise _forbidden(key)
        return current_user

    return dependency


def require_any_permission(*keys: str):
    """Dependency: the user must hold AT LEAST ONE listed permission."""

    def dependency(
        request: Request, current_user: User = Depends(get_current_user)
    ) -> User:
        held = get_permissions(request, current_user)
        if not any(key in held for key in keys):
            raise _forbidden(keys[0])
        return current_user

    return dependency


def has_permission(request: Request, user: User, key: str) -> bool:
    return key in get_permissions(request, user)


def user_has(user: User, key: str) -> bool:
    """Permission check inside a route body, for the result filters that narrow
    a query rather than deny access. Roles are eager-loaded, so this costs no
    query."""
    return key in resolve_permissions(user)


def user_has_role(user: User, slug: str) -> bool:
    return any(role.slug == slug for role in user.roles)
