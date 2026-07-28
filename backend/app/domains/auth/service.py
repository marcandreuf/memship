"""Authentication service — business logic for auth operations."""

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.security.password import hash_password, verify_password
from app.domains.auth.models import User
from app.domains.members.models import Member, MembershipType
from app.domains.members.service import allocate_member_number
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


def _issue_verification_token(user: User) -> str:
    token = secrets.token_urlsafe(32)
    user.verification_token = token
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
        role="member",
        is_active=True,
        email_verified=False,
    )
    db.add(user)
    db.flush()

    # Create member with default membership type
    default_type = (
        db.query(MembershipType)
        .filter(MembershipType.is_active == True)
        .order_by(MembershipType.id)
        .first()
    )

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
    user = (
        db.query(User)
        .filter(User.verification_token == token, User.is_active == True)
        .first()
    )
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


def request_password_reset(db: Session, email: str) -> str | None:
    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user:
        return None

    token = secrets.token_urlsafe(32)
    user.reset_token = token
    user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    db.flush()

    return token


def reset_password(db: Session, token: str, new_password: str) -> bool:
    user = (
        db.query(User)
        .filter(
            User.reset_token == token,
            User.is_active == True,
        )
        .first()
    )
    if not user:
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
