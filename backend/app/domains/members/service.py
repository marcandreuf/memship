"""Member service — business logic for member operations."""

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.domains.members.models import Member, MembershipType
from app.domains.persons.models import Person

VALID_STATUS_TRANSITIONS = {
    "pending": ["active", "cancelled"],
    "active": ["suspended", "cancelled", "expired"],
    "suspended": ["active", "cancelled"],
    "cancelled": [],
    "expired": ["active"],
}

MINOR_AGE_THRESHOLD = 18


def is_minor_by_dob(date_of_birth: date | None) -> bool:
    if not date_of_birth:
        return False
    today = date.today()
    age = today.year - date_of_birth.year - (
        (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
    )
    return age < MINOR_AGE_THRESHOLD


def generate_member_number(db: Session) -> str:
    last_member = (
        db.query(Member)
        .filter(Member.member_number.isnot(None))
        .order_by(Member.id.desc())
        .first()
    )
    if last_member and last_member.member_number:
        try:
            num = int(last_member.member_number.replace("M-", ""))
            return f"M-{num + 1:04d}"
        except ValueError:
            pass
    return "M-0001"


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

    member_number = generate_member_number(db)
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
