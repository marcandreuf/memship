"""Authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.security.dependencies import get_current_user
from app.core.security.jwt import create_access_token
from app.db.session import get_db
from app.domains.auth.models import User
from app.domains.auth.schemas import (
    LoginRequest,
    MessageResponse,
    PasswordReset,
    PasswordResetRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.domains.auth.service import (
    authenticate_user,
    register_user,
    request_password_reset,
    reset_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = authenticate_user(db, data.email, data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if user.is_locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is locked",
        )

    token = create_access_token(user.id, user.role)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,  # TODO: set True in production
        samesite="lax",
        max_age=60 * 30,  # 30 minutes
        path="/",
    )
    db.commit()

    return TokenResponse()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    try:
        user = register_user(
            db,
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.email,
            password=data.password,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    token = create_access_token(user.id, user.role)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 30,
        path="/",
    )
    db.commit()

    member = user.person.member
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        person_id=user.person_id,
        first_name=user.person.first_name,
        last_name=user.person.last_name,
        member_id=member.id if member else None,
        member_number=member.member_number if member else None,
    )


@router.post("/password-reset-request", response_model=MessageResponse)
def password_reset_request(data: PasswordResetRequest, db: Session = Depends(get_db)):
    token = request_password_reset(db, data.email)
    db.commit()

    # In v0.1.0 (no email), return the token directly for dev/testing
    if token:
        return MessageResponse(
            message="Password reset token generated (dev mode — no email sent)",
            reset_token=token,
        )

    # Don't reveal whether email exists
    return MessageResponse(message="If the email exists, a reset token has been generated")


@router.post("/password-reset", response_model=MessageResponse)
def password_reset_confirm(data: PasswordReset, db: Session = Depends(get_db)):
    success = reset_password(db, data.token, data.new_password)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    db.commit()
    return MessageResponse(message="Password reset successful")


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    member = current_user.person.member
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        person_id=current_user.person_id,
        first_name=current_user.person.first_name,
        last_name=current_user.person.last_name,
        member_id=member.id if member else None,
        member_number=member.member_number if member else None,
    )


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response):
    response.delete_cookie(key="access_token", path="/")
    return MessageResponse(message="Logged out")
