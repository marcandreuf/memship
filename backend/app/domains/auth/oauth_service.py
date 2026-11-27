"""Resolve an external provider profile to a memship user."""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.permissions import MEMBER_SLUG
from app.core.schema_types import normalize_email
from app.domains.auth.models import User, UserIdentity
from app.domains.auth.roles import assign_roles
from app.domains.auth.service import get_registration_settings
from app.domains.members.models import Member
from app.domains.members.service import (
    allocate_member_number,
    get_default_membership_type,
)
from app.domains.persons.models import Person


class RegistrationClosedError(Exception):
    """No account exists for this identity and public sign-up is disabled."""


class EmailNotVerifiedError(Exception):
    """The provider did not vouch for the email address."""


class UnverifiedAccountHasHistory(Exception):
    """An unverified account holds financial history, so it cannot be discarded.

    Unreachable once approval requires a verified address (#643): a registration
    nobody confirmed can no longer be approved, so it can hold neither a member
    number nor a receipt. Kept because the alternative failure is worse than the
    exception. ``receipts.party_id`` and ``sepa_mandates.party_id`` carry no
    ``ondelete``, so the database would refuse the delete and the caller would
    see an ``IntegrityError`` out of an authentication callback, which reads as
    a broken sign-in rather than as a refusal.
    """


def _discard_unverified_account(db: Session, user: User) -> None:
    """Delete the party behind an unverified account, so its address is free.

    The **party**, not the ``users`` row. The abandoned registration created a
    Person, a Party and a pending Member, and deleting only the login would
    orphan all three, leave the address sitting on the party row, and hand the
    replacement account a second set of each. Everything else the party owns —
    contacts, addresses, bank accounts, the member record — cascades with it.

    The audit entry is written before the delete and deliberately carries no
    ``user_id``: there is no acting user in a provider callback, and the column
    is ``ON DELETE SET NULL`` against the row being removed, so recording the
    discarded account there would blank itself out. The detail goes in
    ``old_values``, which nothing cascades into.
    """
    from app.domains.audit.models import AuditLog
    from app.domains.billing.models import Receipt, SepaMandate
    from app.domains.persons.models import Party

    party_id = user.party_id
    blocked = (
        db.query(Receipt).filter(Receipt.party_id == party_id).count()
        + db.query(SepaMandate).filter(SepaMandate.party_id == party_id).count()
    )
    if blocked:
        raise UnverifiedAccountHasHistory(user.email)

    db.add(
        AuditLog(
            table_name="party",
            record_id=party_id,
            action="delete",
            user_id=None,
            old_values={
                "email": user.email,
                "user_id": user.id,
                "reason": "unverified account replaced by a provider-verified sign-in",
            },
        )
    )
    db.flush()

    party = db.query(Party).filter(Party.id == party_id).first()
    if party is not None:
        db.delete(party)
    db.flush()


@dataclass
class OAuthProfile:
    provider: str
    subject: str
    email: str
    email_verified: bool
    first_name: str
    last_name: str

    def __post_init__(self) -> None:
        """Normalise here, not at the call site.

        Nothing on this path goes through a request schema, so the address
        arrives exactly as the provider spelled it. It is then matched against
        ``users.email`` to link an existing account, and written to three rows
        when a new one is created — every one of which has to agree with what
        the password paths store (#191).
        """
        self.email = normalize_email(self.email)


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
    if existing is not None and existing.email_verified:
        db.add(
            UserIdentity(
                user_id=existing.id,
                provider=profile.provider,
                provider_subject=profile.subject,
                email=profile.email,
            )
        )
        db.flush()
        return existing, False

    # Read before anything is destroyed. Discarding the unverified account and
    # only then discovering that registration is closed would leave the person
    # with neither their old account nor a new one (#644).
    public_registration, requires_approval = get_registration_settings(db)
    if not public_registration:
        raise RegistrationClosedError(profile.email)

    if existing is not None:
        _discard_unverified_account(db, existing)

    person = Person(
        first_name=profile.first_name or profile.email.split("@")[0],
        last_name=profile.last_name or "",
        email=profile.email,
    )
    db.add(person)
    db.flush()

    # No password hash: this account signs in through the provider only.
    user = User(
        party_id=person.party_id,
        email=profile.email,
        password_hash=None,
        is_active=True,
        email_verified=True,
        email_verified_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.flush()

    # Sign-up through a provider is still a member signing up (#168).
    assign_roles(db, user, MEMBER_SLUG)

    default_type = get_default_membership_type(db)
    member = Member(
        party_id=person.party_id,
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