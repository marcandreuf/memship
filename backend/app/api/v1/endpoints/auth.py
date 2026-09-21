"""Authentication endpoints."""

import json
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.email import (
    send_existing_account_email,
    send_password_reset_email,
    send_verification_email,
)
from app.core.security.dependencies import get_current_user
from app.core.authorization import require_permission, resolve_permissions
from app.core.security.jwt import create_access_token
from app.core.security.oauth import get_provider, provider_redirect_uri
from app.core.security.password import spend_verify_work
from app.core.security.rate_limit import (
    EMAIL_DISPATCH_BY_EMAIL,
    EMAIL_DISPATCH_BY_IP,
    LOGIN_BY_EMAIL,
    LOGIN_BY_IP,
    REGISTER_BY_EMAIL,
    REGISTER_BY_IP,
    client_ip,
    enforce,
    identity_key,
    record,
)
from app.db.session import get_db
from app.domains.auth.models import User
from app.domains.auth.schemas import (
    LoginRequest,
    MessageResponse,
    PasswordReset,
    PasswordResetRequest,
    RegisterRequest,
    RoleSummary,
    RegisterResponse,
    SessionRefreshResponse,
    ResendVerificationRequest,
    SsoProvidersResponse,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)
from app.domains.auth.oauth_service import (
    EmailNotVerifiedError,
    OAuthProfile,
    RegistrationClosedError,
    find_or_create_from_oauth,
)
from app.domains.auth.sso_config import resolve_sso_config
from app.domains.mailing.mailing_config import mailing_enabled
from app.domains.auth.service import (
    EmailTaken,
    authenticate_user,
    get_registration_settings,
    register_user,
    request_password_reset,
    resend_verification,
    reset_password,
    verify_email,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _dev_tokens_allowed() -> bool:
    """Whether a verification / reset token may be returned in the response body.

    Only ever in local development. Anywhere else this is an unauthenticated
    account-takeover primitive: ask for a reset on someone's address, read the
    token out of the 200, set their password.
    """
    return settings.APP_ENV == "development"


def _set_session_cookie(response: Response, user: User) -> None:
    """Issue the session cookie. The single place that decides its flags.

    ``secure`` follows the deployment's own URL scheme (see
    ``settings.session_cookie_secure``) rather than being hardcoded off: on an
    HTTPS install, one plain-HTTP request to the host — an http:// image, a
    typed URL, a captive portal — hands the session to anyone on the path
    before Caddy's redirect fires.
    """
    response.set_cookie(
        key="access_token",
        value=create_access_token(user.id),
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.session_max_age,
        path="/",
    )


@router.post("/login", response_model=TokenResponse)
def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    ip = client_ip(request)
    email = identity_key(data.email)
    enforce((LOGIN_BY_EMAIL, email), (LOGIN_BY_IP, ip))

    user = authenticate_user(db, data.email, data.password)
    if not user:
        # Counted after the check, and only on failure: the window bounds
        # guessing, not ordinary sign-ins from several devices.
        record((LOGIN_BY_EMAIL, email), (LOGIN_BY_IP, ip))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if user.is_locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is locked",
        )

    # Proving the password is not proving the address. Without this, anyone could
    # register with a mailbox they do not own and hold a working session on it —
    # which is what /register already refuses to do by not issuing a cookie of its
    # own ("the account is not usable until the email is confirmed"). Login was
    # handing out the session that endpoint declined to.
    #
    # 403 rather than 401: the credentials were right. The message has to say what
    # to do, because the login form shows it verbatim.
    #
    # Awaiting *approval* is deliberately not checked here. That address is
    # verified, the session is what lets the portal explain the wait, and
    # require_approved_member already closes every feature router behind it.
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Confirm your email address before signing in. Check your inbox "
                "for the confirmation link, or request a new one."
            ),
        )

    # The address is proven, so forget its failures. The source address keeps
    # its count — holding one valid account must not reset a spray from there.
    LOGIN_BY_EMAIL.clear(email)

    _set_session_cookie(response, user)
    db.commit()

    return TokenResponse()


def _verification_url(token: str) -> str:
    return f"{settings.FRONTEND_URL}/{settings.DEFAULT_LOCALE}/verify-email?token={token}"


def _frontend_url(path: str) -> str:
    return f"{settings.FRONTEND_URL}/{settings.DEFAULT_LOCALE}/{path}"


# The one thing /register says, whoever the address turns out to belong to.
REGISTRATION_RECEIVED = "Registration received. Check your email to confirm your address."
REGISTRATION_RECEIVED_DEV = "Registration received (dev mode — no email sent)"


def _registration_received(
    email: str,
    requires_approval: bool,
    *,
    dev: bool = False,
    verification_token: str | None = None,
) -> RegisterResponse:
    """Build the response both branches of ``/register`` return.

    Every field has to be answerable without knowing whether the address was
    already taken, or the body reinstates by its shape the disclosure the status
    code no longer makes (#102):

    - ``email`` is the caller's own input, echoed.
    - ``requires_approval`` is organisation-level and identical for everyone.
    - ``member_status`` follows from ``requires_approval`` alone — a fresh
      registration lands in ``pending``, or in ``active`` when the club approves
      inline — so it is derived here rather than read off a member row that only
      one of the two branches has.
    """
    return RegisterResponse(
        message=REGISTRATION_RECEIVED_DEV if dev else REGISTRATION_RECEIVED,
        email=email,
        member_status="pending" if requires_approval else "active",
        requires_approval=requires_approval,
        verification_token=verification_token,
    )


def _notify_existing_account(db: Session, email: str) -> None:
    """Tell the owner of an address that someone tried to register it.

    What the caller is not told, the owner is. Failures are swallowed: the
    response must not vary with whether this send worked, and an address that
    cannot be mailed is not a reason to answer it differently from one that can.
    """
    user = db.query(User).filter(User.email == email).first()
    if user is None or user.person is None:
        return
    try:
        send_existing_account_email(
            user.email,
            user.person.first_name,
            _frontend_url("login"),
            _frontend_url("forgot-password"),
        )
    except Exception:  # noqa: BLE001 — never let a transport fault shape the reply
        logger.exception("Could not notify an existing account of a signup attempt")


@router.post(
    "/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED
)
def register(data: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    # Every call writes a Person, a User and a Member row, and — once a
    # transport is configured — sends mail. Bounded per source, because keying
    # on the submitted address alone would let a script pick a new one each
    # time, and per address, because a known one is mailed (#102).
    #
    # Both are enforced and recorded before the address is looked up, so the
    # limit a caller hits does not depend on the answer they came for.
    ip = client_ip(request)
    identity = identity_key(data.email)
    enforce((REGISTER_BY_IP, ip), (REGISTER_BY_EMAIL, identity))
    record((REGISTER_BY_IP, ip), (REGISTER_BY_EMAIL, identity))

    public_registration, requires_approval = get_registration_settings(db)
    if not public_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is disabled",
        )

    # Resolved once, before the address is looked up: asking twice would put a
    # second query on one branch and not the other.
    can_mail = mailing_enabled(db)

    # Refuse rather than create an account nobody can reach (#231). Sign-in
    # needs a confirmed address, confirming one needs the link, and the link
    # needs a transport — so registering here used to mint an account that was
    # permanently stuck, told its owner to check an inbox that would never
    # receive anything, and showed the admin an active member. A closed door is
    # the honest answer, and it is visible.
    #
    # This catches an install with no provider configured, which is every
    # self-hosted one before setup. It does not catch a provider that is
    # configured and broken — an invalid API key resolves as usable here and
    # fails at the transport (the counterpart #218 covers). That case still
    # needs the rescue on the member record.
    if not can_mail and not _dev_tokens_allowed():
        logger.error(
            "Registration refused: no mail transport is configured, so the "
            "verification email cannot be sent and the account could never be "
            "used. Configure a provider in Settings → Integrations."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Registration is unavailable: the club has not finished setting "
                "up email. Please contact the club."
            ),
        )

    try:
        user, verification_token = register_user(
            db,
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.email,
            password=data.password,
        )
    except EmailTaken:
        # This used to answer 409 "Email already registered", which the register
        # form rendered verbatim — anyone could read a club's membership off the
        # public signup page one address at a time. It now answers exactly as the
        # branch below does, and the owner is told by mail instead (#102).
        #
        # The argon2 hash `register_user` would have spent is spent anyway. Skip
        # it and the taken address simply returns sooner, which is the same
        # disclosure read off a clock.
        spend_verify_work(data.password)
        if can_mail:
            _notify_existing_account(db, data.email)
        return _registration_received(
            data.email, requires_approval, dev=not can_mail and _dev_tokens_allowed()
        )

    db.commit()

    # No session cookie here: the account is not usable until the email is
    # confirmed and (when configured) an admin approves the registration.
    if can_mail:
        send_verification_email(
            user.email, user.person.first_name, _verification_url(verification_token)
        )
        return _registration_received(data.email, requires_approval)

    # Dev mode — no transport configured, hand the token back like password reset
    # does. The taken-address branch has no token to hand back, so dev mode can
    # tell the two apart where production cannot. That is deliberate and stays:
    # `_dev_tokens_allowed()` gates it, and the mode ships fixed passwords
    # published in this repository, so there is no membership here to disclose.
    if _dev_tokens_allowed():
        return _registration_received(
            data.email, requires_approval, dev=True, verification_token=verification_token
        )

    # Unreachable: the guard above refuses when there is no transport, and dev
    # mode returned the token. Kept as the explicit end of the branch rather
    # than an implicit fall-through returning None.
    return _registration_received(data.email, requires_approval)


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


def _throttle_mail_to(request: Request, email: str) -> None:
    """Bound the two endpoints that mail an address an anonymous caller chose.

    Recorded whatever the outcome, unlike login: both endpoints answer the same
    generic message for a known and an unknown address (so as not to disclose
    which it was), so "did this attempt do anything" is not a distinction the
    handler is allowed to make here either.
    """
    ip = client_ip(request)
    identity = identity_key(email)
    enforce((EMAIL_DISPATCH_BY_EMAIL, identity), (EMAIL_DISPATCH_BY_IP, ip))
    record((EMAIL_DISPATCH_BY_EMAIL, identity), (EMAIL_DISPATCH_BY_IP, ip))


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification_endpoint(
    data: ResendVerificationRequest, request: Request, db: Session = Depends(get_db)
):
    _throttle_mail_to(request, data.email)

    # Nothing to resend through, so say so instead of promising a link that
    # cannot be sent (#231). This discloses the install's state, not the
    # address's, so it is the same answer for everybody.
    if not mailing_enabled(db) and not _dev_tokens_allowed():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Email is not configured for this club, so a verification link "
                "cannot be sent. Please contact the club."
            ),
        )

    result = resend_verification(db, data.email)
    db.commit()

    # Generic response either way — never reveal whether the address exists.
    generic = "If the email exists and is unverified, a new link has been sent"

    if result and mailing_enabled(db):
        user, token = result
        send_verification_email(
            user.email, user.person.first_name, _verification_url(token)
        )
        return MessageResponse(message=generic)

    if result and _dev_tokens_allowed():
        _, token = result
        return MessageResponse(
            message="Verification token generated (dev mode — no email sent)",
            verification_token=token,
        )

    return MessageResponse(message=generic)


@router.post("/password-reset-request", response_model=MessageResponse)
def password_reset_request(
    data: PasswordResetRequest, request: Request, db: Session = Depends(get_db)
):
    _throttle_mail_to(request, data.email)

    token = request_password_reset(db, data.email)
    db.commit()

    generic = "If the email exists, a password reset link has been sent"

    if token:
        # Whichever transport is active sends it — Resend and Gmail/SMTP are
        # interchangeable here. This used to key off SMTP_HOST alone, so a
        # Resend install sent no mail and fell through to the dev branch below,
        # handing the reset token to any anonymous caller.
        if mailing_enabled(db):
            user = db.query(User).filter(User.email == data.email).first()
            reset_url = f"{settings.FRONTEND_URL}/{settings.DEFAULT_LOCALE}/reset-password?token={token}"
            if user:
                send_password_reset_email(user.email, user.person.first_name, reset_url)
            return MessageResponse(message=generic)

        if _dev_tokens_allowed():
            return MessageResponse(
                message="Password reset token generated (dev mode — no email sent)",
                reset_token=token,
            )

        # Production with no transport: the token exists but there is no safe way
        # to deliver it, and returning it would be an account takeover primitive.
        logger.error(
            "Password reset requested but no mail transport is configured — "
            "the token cannot be delivered. Configure a provider in "
            "Settings → Integrations or via RESEND_API_KEY / SMTP_HOST."
        )

    # Don't reveal whether email exists
    return MessageResponse(message=generic)


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
def get_me(current_user: User = Depends(require_permission("self.profile.read"))):
    member = current_user.person.member
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        roles=[
            RoleSummary(id=r.id, slug=r.slug, name=r.name) for r in current_user.roles
        ],
        permissions=sorted(resolve_permissions(current_user)),
        is_active=current_user.is_active,
        person_id=current_user.person_id,
        first_name=current_user.person.first_name,
        last_name=current_user.person.last_name,
        member_id=member.id if member else None,
        member_number=member.member_number if member else None,
        gender=current_user.person.gender,
        photo_url=current_user.person.photo_url,
        email_verified=bool(current_user.email_verified),
        member_status=member.status if member else None,
        session_expires_in=settings.session_max_age,
        session_refresh_after=settings.session_refresh_after,
    )


@router.post("/refresh", response_model=SessionRefreshResponse)
def refresh_session(
    response: Response,
    current_user: User = Depends(get_current_user),
):
    """Slide the session window forward for a client that is still working.

    The cookie is only otherwise issued at login, so a session was an absolute
    window from sign-in: someone mid-form at minute 31 was logged out with no
    warning. This re-issues it — same flags, a fresh token — but only for a
    caller whose current token is still valid, so an idle client past the window
    gets the usual 401 and the timeout still means something.
    """
    _set_session_cookie(response, current_user)
    return SessionRefreshResponse(
        expires_in=settings.session_max_age,
        refresh_after=settings.session_refresh_after,
    )


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response):
    # Same flags as when it was set — a browser ignores a deletion whose
    # attributes do not match.
    response.delete_cookie(
        key="access_token",
        path="/",
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )
    return MessageResponse(message="Logged out")


# --- Single sign-on ---


def _frontend_url(path: str, **params: str) -> str:
    base = f"{settings.FRONTEND_URL.rstrip('/')}/{settings.DEFAULT_LOCALE}{path}"
    if params:
        base += "?" + urlencode(params)
    return base


@router.get("/sso/providers", response_model=SsoProvidersResponse)
def sso_providers(db: Session = Depends(get_db)):
    """Which SSO buttons the login/register pages should render."""
    resolved = resolve_sso_config(db)
    return SsoProvidersResponse(
        google=resolved.google.ready,
        apple=resolved.apple.ready,
    )


@router.get("/oauth/{provider}/login")
async def oauth_login(
    provider: str, request: Request, db: Session = Depends(get_db)
):
    client = get_provider(provider, resolve_sso_config(db))
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SSO provider '{provider}' is not configured",
        )

    # Apple only returns the email and name claims when the response is posted
    # back, which also makes the callback a POST.
    extra = {"response_mode": "form_post"} if provider == "apple" else {}

    # authlib stores the CSRF `state` and the OIDC `nonce` in the signed session
    # cookie and checks both on the way back.
    return await client.authorize_redirect(
        request, provider_redirect_uri(provider), **extra
    )


async def _apple_form_name(request: Request) -> tuple[str, str]:
    """Read the name Apple posts back, which it only ever sends once.

    Apple includes a `user` field with the person's name on the **first**
    authorization only; every later sign-in omits it. Must be read before
    authlib consumes (and closes) the form.
    """
    try:
        form = await request.form()
    except Exception:
        return "", ""

    raw = form.get("user")
    if not raw:
        return "", ""
    try:
        name = json.loads(raw).get("name") or {}
    except (ValueError, TypeError):
        return "", ""
    return name.get("firstName") or "", name.get("lastName") or ""


@router.api_route("/oauth/{provider}/callback", methods=["GET", "POST"])
async def oauth_callback(
    provider: str, request: Request, db: Session = Depends(get_db)
):
    client = get_provider(provider, resolve_sso_config(db))
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SSO provider '{provider}' is not configured",
        )

    # Apple posts the profile name in the form body; grab it before authlib
    # reads and closes the form.
    apple_first, apple_last = ("", "")
    if provider == "apple" and request.method == "POST":
        apple_first, apple_last = await _apple_form_name(request)

    try:
        token = await client.authorize_access_token(request)
    except Exception:
        # Covers a denied consent screen, a replayed/expired code and a failed
        # state or id_token check. None of it is actionable by the user beyond
        # trying again, and echoing provider errors back would leak detail.
        return RedirectResponse(_frontend_url("/login", error="sso_failed"))

    claims = token.get("userinfo") or {}
    subject = claims.get("sub")
    email = claims.get("email")
    if not subject or not email:
        return RedirectResponse(_frontend_url("/login", error="sso_failed"))
    if not email.isascii():
        # The provider's address never passes through the ``Email`` type, so
        # the ASCII rule that keeps the application and the unique index
        # folding case the same way (#242) has to be applied here by hand.
        return RedirectResponse(_frontend_url("/login", error="sso_email_unsupported"))

    # Apple sends email_verified as the string "true"/"false" rather than a bool.
    raw_verified = claims.get("email_verified")
    email_verified = (
        raw_verified.lower() == "true"
        if isinstance(raw_verified, str)
        else bool(raw_verified)
    )

    profile = OAuthProfile(
        provider=provider,
        subject=subject,
        email=email,
        email_verified=email_verified,
        first_name=claims.get("given_name") or apple_first,
        last_name=claims.get("family_name") or apple_last,
    )

    try:
        user, _created = find_or_create_from_oauth(db, profile)
    except EmailNotVerifiedError:
        return RedirectResponse(_frontend_url("/login", error="sso_email_unverified"))
    except RegistrationClosedError:
        return RedirectResponse(_frontend_url("/login", error="registration_closed"))

    if not user.is_active:
        return RedirectResponse(_frontend_url("/login", error="account_disabled"))
    if user.is_locked:
        return RedirectResponse(_frontend_url("/login", error="account_locked"))

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    # A pending member still gets a session — the portal shows them the
    # "awaiting approval" screen rather than a dead end.
    response = RedirectResponse(_frontend_url("/dashboard"))
    _set_session_cookie(response, user)
    return response
