"""Authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.email import (
    send_password_reset_email,
    send_verification_email,
)
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
    RegisterResponse,
    ResendVerificationRequest,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)
from app.domains.auth.service import (
    authenticate_user,
    get_registration_settings,
    register_user,
    request_password_reset,
    resend_verification,
    reset_password,
    verify_email,
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


def _verification_url(token: str) -> str:
    return f"{settings.FRONTEND_URL}/{settings.DEFAULT_LOCALE}/verify-email?token={token}"


@router.post(
    "/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED
)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    public_registration, requires_approval = get_registration_settings(db)
    if not public_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is disabled",
        )

    try:
        user, verification_token = register_user(
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

    member = user.person.member
    member_status = member.status if member else "pending"
    db.commit()

    # No session cookie here: the account is not usable until the email is
    # confirmed and (when configured) an admin approves the registration.
    if settings.email_enabled:
        send_verification_email(
            user.email, user.person.first_name, _verification_url(verification_token)
        )
        return RegisterResponse(
            message="Registration received. Check your email to confirm your address.",
            email=user.email,
            member_status=member_status,
            requires_approval=requires_approval,
        )

    # Dev mode — no transport configured, hand the token back like password reset does
    return RegisterResponse(
        message="Registration received (dev mode — no email sent)",
        email=user.email,
        member_status=member_status,
        requires_approval=requires_approval,
        verification_token=verification_token,
    )


@router.post("/verify-email", response_model=MessageResponse)
def verify_email_endpoint(data: VerifyEmailRequest, db: Session = Depends(get_db)):
    user = verify_email(db, data.token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )
    db.commit()
    return MessageResponse(message="Email verified")


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification_endpoint(
    data: ResendVerificationRequest, db: Session = Depends(get_db)
):
    result = resend_verification(db, data.email)
    db.commit()

    # Generic response either way — never reveal whether the address exists.
    generic = "If the email exists and is unverified, a new link has been sent"

    if result and settings.email_enabled:
        user, token = result
        send_verification_email(
            user.email, user.person.first_name, _verification_url(token)
        )
        return MessageResponse(message=generic)

    if result:
        _, token = result
        return MessageResponse(
            message="Verification token generated (dev mode — no email sent)",
            verification_token=token,
        )

    return MessageResponse(message=generic)


@router.post("/password-reset-request", response_model=MessageResponse)
def password_reset_request(data: PasswordResetRequest, db: Session = Depends(get_db)):
    token = request_password_reset(db, data.email)
    db.commit()

    if token:
        if settings.smtp_enabled:
            # Send reset email
            user = db.query(User).filter(User.email == data.email).first()
            reset_url = f"{settings.FRONTEND_URL}/es/reset-password?token={token}"
            if user:
                send_password_reset_email(user.email, user.person.first_name, reset_url)
            return MessageResponse(
                message="If the email exists, a password reset link has been sent"
            )
        else:
            # Dev mode — return token directly
            return MessageResponse(
                message="Password reset token generated (dev mode — no email sent)",
                reset_token=token,
            )

    # Don't reveal whether email exists
    return MessageResponse(message="If the email exists, a password reset link has been sent")


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
        gender=current_user.person.gender,
        email_verified=bool(current_user.email_verified),
        member_status=member.status if member else None,
    )


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response):
    response.delete_cookie(key="access_token", path="/")
    return MessageResponse(message="Logged out")
