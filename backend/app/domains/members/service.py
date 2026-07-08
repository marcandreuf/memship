"""Member service — business logic for member operations."""

from datetime import date, datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Query, Session, joinedload

from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person

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
        search_term = f"%{search}%"
        query = query.join(Person, Member.person_id == Person.id).filter(
            (Person.first_name.ilike(search_term))
            | (Person.last_name.ilike(search_term))
            | (Person.email.ilike(search_term))
            | (Member.member_number.ilike(search_term))
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
    guardian_person_id: int | None = None,
    internal_notes: str | None = None,
) -> Member:
    person = Person(
        first_name=first_name,
        last_name=last_name,
        email=email,
        date_of_birth=date_of_birth,
        gender=gender,
        national_id=national_id,
    )
    db.add(person)
    db.flush()

    member_number = allocate_member_number(db)
    minor = is_minor_by_dob(date_of_birth)

    member = Member(
        person_id=person.id,
        membership_type_id=membership_type_id,
        member_number=member_number,
        status="pending",
        is_minor=minor,
        guardian_person_id=guardian_person_id,
        internal_notes=internal_notes,
    )
    db.add(member)
    db.flush()

    return member


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
