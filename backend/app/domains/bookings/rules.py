"""The booking rules an organization configures in ``features``.

``features`` is free-form JSON, so these keys are checked twice: on the way in,
where an invalid value is refused, and on the way out, where a value stored
before the check existed falls back to its default instead of failing every
availability, booking and cancellation request with a 500.

The machinery moved to ``domains/shared/feature_rules.py`` when the same pattern
was extended to the billing values (#493). Two copies of "what counts as a valid
integer here" would have been free to disagree, and the public names below are
unchanged so no caller had to move.
"""

from app.domains.shared.feature_rules import IntRules, int_rule as _int_rule
from app.domains.shared.feature_rules import validate_int_rules

#: key -> (default, minimum, maximum). The maximum keeps ``timedelta`` from
#: overflowing on an absurd value.
INT_RULES: IntRules = {
    "booking_window_days": (14, 1, 365),
    "booking_cancellation_deadline_hours": (24, 0, 8760),
}


def validate_booking_rules(features: dict) -> dict:
    return validate_int_rules(features, INT_RULES)


def int_rule(features: dict, key: str) -> int:
    return _int_rule(features, key, INT_RULES)
