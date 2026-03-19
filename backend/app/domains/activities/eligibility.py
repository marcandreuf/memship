"""Eligibility checking for activity registration."""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.domains.activities.models import Activity, Registration
from app.domains.members.models import Member


@dataclass
class EligibilityResult:
    eligible: bool = True
    reasons: list[str] = field(default_factory=list)

    def add_reason(self, reason: str) -> None:
        self.eligible = False
        self.reasons.append(reason)


def check_eligibility(
    db: Session, activity: Activity, member: Member
) -> EligibilityResult:
    """Check if a member is eligible to register for an activity."""
    result = EligibilityResult()
    now = datetime.now(timezone.utc)

    # 1. Activity must be published
    if activity.status != "published":
        result.add_reason("Activity is not open for registration")
        return result

    # 2. Member must be active
    if member.status != "active":
        result.add_reason("Member status is not active")

    # 3. Membership type restriction
    if activity.allowed_membership_types:
        if (
            not member.membership_type_id
            or member.membership_type_id not in activity.allowed_membership_types
        ):
            result.add_reason("Membership type is not eligible for this activity")

    # 4. Age restriction
    if member.person and member.person.date_of_birth:
        age = _calculate_age(member.person.date_of_birth, activity.starts_at.date())
        if activity.min_age is not None and age < activity.min_age:
            result.add_reason(f"Minimum age is {activity.min_age}")
        if activity.max_age is not None and age > activity.max_age:
            result.add_reason(f"Maximum age is {activity.max_age}")

    # 5. Registration window
    if now < activity.registration_starts_at:
        result.add_reason("Registration has not opened yet")
    if now > activity.registration_ends_at:
        result.add_reason("Registration is closed")

    # 6. Already registered (non-cancelled)
    existing = (
        db.query(Registration)
        .filter(
            Registration.activity_id == activity.id,
            Registration.member_id == member.id,
            Registration.status != "cancelled",
        )
        .first()
    )
    if existing:
        result.add_reason("Already registered for this activity")

    return result


def _calculate_age(date_of_birth: date, reference_date: date) -> int:
    """Calculate age at a reference date."""
    age = reference_date.year - date_of_birth.year
    if (reference_date.month, reference_date.day) < (
        date_of_birth.month,
        date_of_birth.day,
    ):
        age -= 1
    return age
