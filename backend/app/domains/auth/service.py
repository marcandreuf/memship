"""Authentication service — business logic for auth operations."""

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.security.password import hash_password, verify_password
from app.domains.auth.models import User
from app.domains.members.models import Member, MembershipType
from app.domains.persons.models import Person


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    db.flush()
    return user


def register_user(
    db: Session,
    first_name: str,
    last_name: str,
    email: str,
    password: str,
) -> User:
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

    # Generate next member number
    last_member = (
        db.query(Member)
        .filter(Member.member_number.isnot(None))
        .order_by(Member.id.desc())
        .first()
    )
    if last_member and last_member.member_number:
        try:
            num = int(last_member.member_number.replace("M-", ""))
            next_number = f"M-{num + 1:04d}"
        except ValueError:
            next_number = f"M-{person.id:04d}"
    else:
        next_number = "M-0001"

    member = Member(
        person_id=person.id,
        user_id=user.id,
        membership_type_id=default_type.id if default_type else None,
        member_number=next_number,
        status="pending",
    )
    db.add(member)
    db.flush()

    return user


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
