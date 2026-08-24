"""FastAPI dependencies for authentication."""

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security.jwt import decode_access_token
from app.db.session import get_db
from app.domains.auth.models import User


def _subject_id(payload: dict) -> int | None:
    """The user id in a token's ``sub``, or None if it is not usable.

    A token can carry a valid signature and still be unusable: no ``sub`` at
    all, or one that is not numeric. Reading it as ``int(payload["sub"])`` turned
    those into a KeyError or ValueError escaping the dependency, so the caller
    got a 500 where the honest answer is 401 — an authentication failure
    reported as a server fault, and noise in any error budget watching 5xx.
    """
    sub = payload.get("sub")
    if sub is None:
        return None
    try:
        return int(sub)
    except (TypeError, ValueError):
        return None


def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = decode_access_token(access_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id = _subject_id(payload)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    if user.is_locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is locked",
        )

    return user


def require_approved_member(current_user: User = Depends(get_current_user)) -> User:
    """Block members whose registration is still awaiting admin approval.

    A pending member can authenticate and keep a session (so the portal can show
    them *why* they are blocked), but every feature router guarded by this
    dependency stays closed until an admin approves the registration.

    Only ``pending`` is blocked here. Suspended / cancelled / expired members are
    a separate lifecycle concern that the domain rules (activity eligibility,
    member card status, billing) already handle with far better errors than a
    blanket 403 — widening this gate would swallow those messages. Staff always
    pass, as does any user with no member record (staff accounts created
    directly).
    """
    # Imported here because app.core.authorization imports get_current_user from
    # this module.
    from app.core.authorization import is_staff, resolve_permissions

    if is_staff(resolve_permissions(current_user)):
        return current_user

    member = current_user.person.member if current_user.person else None
    if member is not None and member.status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "pending_approval", "member_status": member.status},
        )

    return current_user


def get_optional_user(
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    if not access_token:
        return None

    payload = decode_access_token(access_token)
    if payload is None:
        return None

    user_id = _subject_id(payload)
    if user_id is None:
        return None
    return db.query(User).filter(User.id == user_id, User.is_active == True).first()
