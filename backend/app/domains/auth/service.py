"""Authentication service — business logic for auth operations."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.permissions import SUPER_ADMIN_SLUG
from app.core.security.password import hash_password, verify_password
from app.domains.auth.models import User
from app.domains.auth.roles import assign_roles
from app.domains.members.models import Member
from app.domains.members.service import (
    allocate_member_number,
    get_default_membership_type,
)
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person

VERIFICATION_TOKEN_TTL_HOURS = 24


def get_registration_settings(db: Session) -> tuple[bool, bool]:
    """Return ``(public_registration, registration_requires_approval)``.

    Both default to True when the org row or the flag is absent: a fresh install
    accepts public sign-ups and holds them for admin approval.
    """
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    features = (org.features if org and org.features else {}) or {}
    return (
        features.get("public_registration", True),
        features.get("registration_requires_approval", True),
    )


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user:
        return None
    # SSO-only accounts have no password hash — they cannot log in on this path.
    if not user.password_hash:
        return None
    if not verify_password(password, user.password_hash):
        return None
    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    db.flush()
    return user


def token_digest(token: str) -> str:
    """What the users table holds in place of a recovery token.

    The verification and reset tokens are single-factor account recovery, so
    the row stores a SHA-256 of the token rather than the token itself: a read
    of the table (a backup, a log, a stray SELECT) yields nothing usable, and
    the lookup below compares digests — an attacker who could time the SQL
    equality would be timing a hash they cannot invert, not the secret.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def _find_by_token(db: Session, column, token: str) -> User | None:
    """Look an active user up by a recovery token, comparing in constant time.

    The digest narrows the query; ``compare_digest`` over the stored value is
    the check that decides, so no byte of the comparison leaks through timing
    even if the database lookup were to.
    """
    digest = token_digest(token)
    user = db.query(User).filter(column == digest, User.is_active == True).first()
    if user is None:
        return None
    stored = getattr(user, column.key) or ""
    if not hmac.compare_digest(stored, digest):
        return None
    return user


def _issue_verification_token(user: User) -> str:
    token = secrets.token_urlsafe(32)
    user.verification_token = token_digest(token)
    user.verification_token_expires_at = datetime.now(timezone.utc) + timedelta(
        hours=VERIFICATION_TOKEN_TTL_HOURS
    )
    return token


def register_user(
    db: Session,
    first_name: str,
    last_name: str,
    email: str,
    password: str,
) -> tuple[User, str]:
    """Create a self-registered member and return ``(user, verification_token)``.

    The member lands in ``pending`` with **no member number** — the number is
    allocated on approval (see ``members.service.approve_registration``). When the
    org has turned ``registration_requires_approval`` off, the registration is
    approved inline so the member is immediately active.
    """
    # Check if email already exists
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise ValueError("Email already registered")

    # Create person
    person = Person(
        first_name=first_name,
        last_name=last_name,
        email=email,
    )
    db.add(person)
    db.flush()

    # Create user
    user = User(
        person_id=person.id,
        email=email,
        password_hash=hash_password(password),
        is_active=True,
        email_verified=False,
    )
    db.add(user)
    db.flush()

    assign_roles(db, user)

    default_type = get_default_membership_type(db)

    member = Member(
        person_id=person.id,
        user_id=user.id,
        membership_type_id=default_type.id if default_type else None,
        member_number=None,
        status="pending",
    )
    db.add(member)
    db.flush()

    _, requires_approval = get_registration_settings(db)
    if not requires_approval:
        member.member_number = allocate_member_number(db)
        member.status = "active"
        member.status_changed_at = datetime.now(timezone.utc)
        db.flush()

    token = _issue_verification_token(user)
    db.flush()

    return user, token


def verify_email(db: Session, token: str) -> User | None:
    """Consume a verification token. Returns the user, or None if invalid/expired."""
    user = _find_by_token(db, User.verification_token, token)
    if not user:
        return None

    if (
        user.verification_token_expires_at is None
        or user.verification_token_expires_at < datetime.now(timezone.utc)
    ):
        return None

    user.email_verified = True
    user.email_verified_at = datetime.now(timezone.utc)
    user.verification_token = None
    user.verification_token_expires_at = None
    db.flush()

    return user


def resend_verification(db: Session, email: str) -> tuple[User, str] | None:
    """Reissue a verification token. Returns None when there is nothing to send."""
    user = (
        db.query(User)
        .filter(
            User.email == email,
            User.is_active == True,
            User.email_verified == False,
        )
        .first()
    )
    if not user:
        return None

    token = _issue_verification_token(user)
    db.flush()
    return user, token


def is_super_admin(user: User) -> bool:
    return any(role.slug == SUPER_ADMIN_SLUG for role in user.roles)


def request_password_reset(db: Session, email: str) -> str | None:
    """Issue a reset token, or ``None`` when this address cannot use the flow.

    Super admins are excluded. The account holds ``RESERVED_KEYS`` — roles and
    credentials — so letting an email inbox stand in for it makes mailbox access
    equivalent to owning the instance. Their password is reset from the host
    instead, with `python -m app.cli.seed`, which needs shell access to the
    machine running the containers. That also keeps recovery working on an
    install where SMTP was never configured, which is every install on day one.
    """
    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user:
        return None
    if is_super_admin(user):
        # Same `None` as an unknown address, so the endpoint's generic response
        # stays generic and the flow does not disclose who the super admins are.
        return None

    token = secrets.token_urlsafe(32)
    user.reset_token = token_digest(token)
    user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    db.flush()

    return token


def reset_password(db: Session, token: str, new_password: str) -> bool:
    user = _find_by_token(db, User.reset_token, token)
    if not user:
        return False

    # No token is ever issued for a super admin now, but one issued before that
    # rule existed would still be live and inside its hour. Refusing here means
    # the rule holds for tokens already in flight, not just future ones.
    if is_super_admin(user):
        return False

    if (
        user.reset_token_expires_at is None
        or user.reset_token_expires_at < datetime.now(timezone.utc)
    ):
        return False

    user.password_hash = hash_password(new_password)
    user.reset_token = None
    user.reset_token_expires_at = None
    db.flush()

    return True
