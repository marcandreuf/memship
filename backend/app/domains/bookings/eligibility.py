"""Who may book a space.

``Space.allowed_membership_types`` mirrors ``Activity.allowed_membership_types``:
a list of membership type ids, and an empty or NULL list means the space is open
to every member. The check itself is the one in ``activities/eligibility.py``.

Where this parts company with activities is the answer it gives back. Activities
collapse both failures into one sentence, but a member reads them very
differently: "the tier you hold is not one of the tiers this space is for" is a
reason to upgrade, while "you hold no tier at all" is an administrative gap the
club has to close. The two carry separate reason codes so the UI can say the
right thing, and the message text follows the code.
"""

from dataclasses import dataclass

from app.domains.bookings.models import Space
from app.domains.members.models import Member

#: The member holds a tier, but it is not on the space's allow-list.
MEMBERSHIP_TYPE_NOT_ALLOWED = "membership_type_not_allowed"
#: The member holds no tier at all, so no allow-list can ever match.
NO_MEMBERSHIP_TYPE = "no_membership_type"

_MESSAGES = {
    MEMBERSHIP_TYPE_NOT_ALLOWED: "Your membership type does not include this space",
    NO_MEMBERSHIP_TYPE: "You have no membership type assigned",
}


@dataclass(frozen=True)
class SpaceEligibility:
    eligible: bool
    reason: str | None = None

    @property
    def message(self) -> str | None:
        return _MESSAGES.get(self.reason) if self.reason else None


ELIGIBLE = SpaceEligibility(eligible=True)


def check_space_eligibility(space: Space, member: Member) -> SpaceEligibility:
    """Whether ``member`` may hold a booking in ``space``."""
    allowed = space.allowed_membership_types
    if not allowed:
        return ELIGIBLE
    if not member.membership_type_id:
        return SpaceEligibility(eligible=False, reason=NO_MEMBERSHIP_TYPE)
    if member.membership_type_id not in allowed:
        return SpaceEligibility(
            eligible=False, reason=MEMBERSHIP_TYPE_NOT_ALLOWED
        )
    return ELIGIBLE
