"""FastAPI dependencies for authentication."""

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security.jwt import decode_access_token
from app.db.session import get_db
from app.domains.auth.models import User


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

    user_id = int(payload["sub"])
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


def get_optional_user(
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    if not access_token:
        return None

    payload = decode_access_token(access_token)
    if payload is None:
        return None

    user_id = int(payload["sub"])
    return db.query(User).filter(User.id == user_id, User.is_active == True).first()
