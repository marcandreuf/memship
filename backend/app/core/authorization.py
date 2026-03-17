"""Role-based access control helpers."""

from functools import wraps

from fastapi import Depends, HTTPException, status

from app.core.security.dependencies import get_current_user
from app.domains.auth.models import User

ROLE_HIERARCHY = {
    "super_admin": 4,
    "admin": 3,
    "restricted": 2,
    "member": 1,
}


def require_role(minimum_role: str):
    """Dependency that enforces a minimum role level."""
    min_level = ROLE_HIERARCHY.get(minimum_role, 0)

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        user_level = ROLE_HIERARCHY.get(current_user.role, 0)
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return dependency


require_admin = require_role("admin")
require_super_admin = require_role("super_admin")
