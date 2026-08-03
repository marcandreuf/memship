"""Resolve an external provider profile to a memship user."""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domains.auth.models import User, UserIdentity
from app.domains.auth.roles import assign_roles
from app.domains.auth.service import get_registration_settings
from app.domains.members.models import Member, MembershipType
from app.domains.members.service import allocate_member_number
from app.domains.persons.models import Person


class RegistrationClosedError(Exception):
    """No account exists for this identity and public sign-up is disabled."""


class EmailNotVerifiedError(Exception):
    """The provider did not vouch for the email address."""


@dataclass
class OAuthProfile:
    provider: str
    subject: str
    email: str
    email_verified: bool
    first_name: str
    last_name: str


def find_or_create_from_oauth(db: Session, profile: OAuthProfile) -> tuple[User, bool]:
    """Return ``(user, created)`` for an external identity.

    Resolution order:

    1. A known ``(provider, subject)`` — the returning case.
    2. A user with the same email — links the new identity to the existing
       account so signing in with Google after registering with a password
       lands on the same member.
    3. Otherwise create person + user + pending member.

    Step 2 is why an unverified provider email is rejected outright: without
    that check, anyone able to create an account at the provider with someone
    else's address could link into — and then sign in as — that member.
    """
    if not profile.email_verified:
        raise EmailNotVerifiedError(profile.email)

    identity = (
        db.query(UserIdentity)
        .filter(
            UserIdentity.provider == profile.provider,
            UserIdentity.provider_subject == profile.subject,
        )
        .first()
    )
    if identity is not None:
        return identity.user, False

    existing = db.query(User).filter(User.email == profile.email).first()
    if existing is not None:
        db.add(
            UserIdentity(
                user_id=existing.id,
                provider=profile.provider,
                provider_subject=profile.subject,
                email=profile.email,
            )
        )
        # The provider has vouched for the address, so a member who registered
        # with a password but never clicked the link is now confirmed.
        if not existing.email_verified:
            existing.email_verified = True
            existing.email_verified_at = datetime.now(timezone.utc)
            existing.verification_token = None
            existing.verification_token_expires_at = None
        db.flush()
        return existing, False

    public_registration, requires_approval = get_registration_settings(db)
    if not public_registration:
        raise RegistrationClosedError(profile.email)

    person = Person(
        first_name=profile.first_name or profile.email.split("@")[0],
        last_name=profile.last_name or "",
        email=profile.email,
    )
    db.add(person)
    db.flush()

    # No password hash: this account signs in through the provider only.
    user = User(
        person_id=person.id,
        email=profile.email,
        password_hash=None,
        is_active=True,
        email_verified=True,
        email_verified_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.flush()

    assign_roles(db, user)

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

    if not requires_approval:
        member.member_number = allocate_member_number(db)
        member.status = "active"
        member.status_changed_at = datetime.now(timezone.utc)

    db.add(
        UserIdentity(
            user_id=user.id,
            provider=profile.provider,
            provider_subject=profile.subject,
            email=profile.email,
        )
    )
    db.flush()

    return user, True