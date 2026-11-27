"""Member service — business logic for member operations."""

from datetime import date, datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Query, Session, joinedload

from app.core.search import match_words
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Party, Person
from app.domains.persons.service import change_person_email, set_primary_email_contact

VALID_STATUS_TRANSITIONS = {
    "pending": ["active", "cancelled"],
    "active": ["suspended", "cancelled", "expired"],
    "suspended": ["active", "cancelled"],
    "cancelled": [],
    "expired": ["active"],
}

MINOR_AGE_THRESHOLD = 18


def build_members_query(
    db: Session,
    *,
    search: str | None = None,
    status: str | None = None,
    group_id: int | None = None,
) -> Query:
    """Build the filtered members query shared by the list and CSV export.

    Keeping the filter/join logic in one place guarantees the export returns the
    same rows the admin sees in the list.
    """
    query = db.query(Member).options(
        joinedload(Member.person),
        joinedload(Member.membership_type),
        joinedload(Member.guardian),
    )

    if group_id is not None:
        query = query.join(
            MembershipType, Member.membership_type_id == MembershipType.id
        ).filter(MembershipType.group_id == group_id)

    if search:
        query = (
            query.join(Person, Member.party_id == Person.party_id)
            .join(Party, Party.id == Person.party_id)
            .filter(
                match_words(
                    search,
                    Person.first_name,
                    Person.last_name,
                    Party.email,
                    Member.member_number,
                )
            )
        )

    if status:
        query = query.filter(Member.status == status)

    return query.order_by(Member.id.desc())


def is_minor_by_dob(date_of_birth: date | None) -> bool:
    if not date_of_birth:
        return False
    today = date.today()
    age = today.year - date_of_birth.year - (
        (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
    )
    return age < MINOR_AGE_THRESHOLD


def get_default_membership_type(db: Session) -> MembershipType | None:
    """The tier a new sign-up lands on.

    At most one row carries ``is_default`` and the database refuses to mark a
    priced one, so whatever comes back is free. ``is_active`` is deliberately
    not filtered: an admin who hides the default should get a harmless free tier
    on the member rather than a NULL ``membership_type_id``, which bars them
    from every activity that restricts allowed membership types.
    """
    return (
        db.query(MembershipType).filter(MembershipType.is_default == True).first()
    )


def allocate_member_number(db: Session) -> str:
    """Allocate the next member number from the configured prefix + sequence.

    Format is ``prefix + str(next).zfill(padding)`` (e.g. ``SCB-0001``), read from
    the single-tenant ``organization_settings`` row. Race-safe within the tenant
    via ``SELECT ... FOR UPDATE`` on that row, advancing the counter past any
    existing collision. When no settings row exists (minimal setups) it falls
    back to a bare zero-padded sequence derived from the current member count.
    """
    org = (
        db.query(OrganizationSettings)
        .filter(OrganizationSettings.id == 1)
        .with_for_update()
        .first()
    )
    if org is not None:
        prefix = org.member_number_prefix or ""
        padding = org.member_number_padding or 4
        next_num = org.member_number_next or 1
    else:
        prefix = ""
        padding = 4
        next_num = (db.query(func.count(Member.id)).scalar() or 0) + 1

    while True:
        candidate = f"{prefix}{str(next_num).zfill(padding)}"
        collision = (
            db.query(Member.id).filter(Member.member_number == candidate).first()
        )
        next_num += 1
        if not collision:
            break

    if org is not None:
        org.member_number_next = next_num
    return candidate


def assign_missing_member_numbers(db: Session) -> int:
    """Assign a member number to every member that lacks one, in id order.

    Returns the number of members updated. Respects the configured prefix by
    routing each allocation through :func:`allocate_member_number`.
    """
    members = (
        db.query(Member)
        .filter(Member.member_number.is_(None))
        .order_by(Member.id)
        .all()
    )
    for member in members:
        member.member_number = allocate_member_number(db)
        db.flush()
    return len(members)


def create_member(
    db: Session,
    first_name: str,
    last_name: str,
    email: str | None = None,
    date_of_birth=None,
    gender: str | None = None,
    national_id: str | None = None,
    membership_type_id: int | None = None,
    guardian_party_id: int | None = None,
    internal_notes: str | None = None,
) -> Member:
    person = Person(
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date_of_birth,
        gender=gender,
        national_id=national_id,
    )
    db.add(person)
    db.flush()
    # Through the contact, not onto the column: `party.email` is a cache the
    # trigger maintains, and a creator that writes it directly leaves the two
    # disagreeing from birth — after which clearing the address cannot clear a
    # column nothing points at (#473).
    set_primary_email_contact(db, person.party_id, email)

    member_number = allocate_member_number(db)
    minor = is_minor_by_dob(date_of_birth)

    member = Member(
        party_id=person.party_id,
        membership_type_id=membership_type_id,
        member_number=member_number,
        status="pending",
        is_minor=minor,
        guardian_party_id=guardian_party_id,
        internal_notes=internal_notes,
    )
    db.add(member)
    db.flush()

    return member


class EmailNotVerified(ValueError):
    """The applicant never proved they hold the address on the account.

    Its own type, like ``EmailTaken``, because the endpoint answers 403 for this
    and 400 for every other refusal ``approve_registration`` raises. The request
    was well formed and the caller was entitled to make it; the account is not
    in a state that may be approved, which is the same distinction the login
    gate draws when it answers 403 to correct credentials on an unconfirmed
    address.
    """


def change_member_email(db: Session, member: Member, email: str | None) -> None:
    """Write a member's address to the party row and to their User row, if any.

    The rule and the reason it exists live in ``persons.service``, which is
    where the second caller of it is (#636). This stays as the member-shaped
    entry point because that is what the member update endpoint has.
    """
    change_person_email(db, member.person, email)


def change_member_status(
    db: Session, member: Member, new_status: str, reason: str | None = None
) -> Member:
    allowed = VALID_STATUS_TRANSITIONS.get(member.status, [])
    if new_status not in allowed:
        raise ValueError(
            f"Cannot transition from '{member.status}' to '{new_status}'. "
            f"Allowed: {allowed}"
        )

    member.status = new_status
    member.status_reason = reason
    member.status_changed_at = datetime.now(timezone.utc)

    if new_status == "cancelled":
        member.is_active = False

    db.flush()
    return member


def approve_registration(
    db: Session, member: Member, membership_type_id: int | None = None
) -> Member:
    """Approve a pending self-registration: allocate a member number, activate.

    The member number is deliberately allocated here rather than at sign-up, so
    rejected/abandoned registrations never burn a number.

    ``membership_type_id`` is where a paid tier legitimately enters the system:
    a human looked at the applicant and chose it. Any active tier is accepted,
    priced or not; age limits are not checked here on purpose, because the rule
    is warn-not-block and the browser already holds everything the warning
    needs. Omitting it leaves the applicant on whatever the sign-up assigned —
    the free default — and only fills that in when the row somehow has no tier
    at all, since a NULL one bars the member from every activity that restricts
    membership types.
    """
    if member.status != "pending":
        raise ValueError(f"Only pending registrations can be approved (is '{member.status}')")

    # After the status check, so approving an already-active member still gets
    # the clearer error about its status rather than one about its address.
    #
    # Keyed on the account, not on the member: a member an administrator created
    # by hand has no ``users`` row and so no verification state at all, and a
    # check written over the member would refuse every one of them (#643).
    if member.user is not None and not member.user.email_verified:
        raise EmailNotVerified(
            "This member has not confirmed their email address. Ask them to use "
            "the confirmation link before approving the registration."
        )

    if membership_type_id is not None:
        membership_type = (
            db.query(MembershipType)
            .filter(MembershipType.id == membership_type_id)
            .first()
        )
        if membership_type is None:
            raise ValueError(f"Membership type {membership_type_id} does not exist")
        if not membership_type.is_active:
            raise ValueError(
                f"Membership type '{membership_type.name}' is not active"
            )
        member.membership_type_id = membership_type.id
    elif member.membership_type_id is None:
        default_type = get_default_membership_type(db)
        if default_type is not None:
            member.membership_type_id = default_type.id

    if not member.member_number:
        member.member_number = allocate_member_number(db)

    member.status = "active"
    member.status_reason = None
    member.status_changed_at = datetime.now(timezone.utc)
    db.flush()
    return member


def reject_registration(db: Session, member: Member, reason: str | None = None) -> Member:
    """Reject a pending self-registration and disable the linked login."""
    if member.status != "pending":
        raise ValueError(f"Only pending registrations can be rejected (is '{member.status}')")

    member.status = "cancelled"
    member.status_reason = reason
    member.status_changed_at = datetime.now(timezone.utc)
    member.is_active = False

    if member.user is not None:
        member.user.is_active = False

    db.flush()
    return member
