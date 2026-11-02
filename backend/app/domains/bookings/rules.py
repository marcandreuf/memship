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
from app.domains.shared.feature_rules import validate_bool_keys, validate_int_rules

#: key -> (default, minimum, maximum). The maximum keeps ``timedelta`` from
#: overflowing on an absurd value.
INT_RULES: IntRules = {
    "booking_window_days": (14, 1, 365),
    "booking_cancellation_deadline_hours": (24, 0, 8760),
}


#: Read as a boolean, through `bool(features.get(key, True))` in
#: `bookings/service.py`, so it cannot raise. The check refuses the string
#: `"false"`, which is truthy and would switch the waitlist on for an admin who
#: meant to switch it off. Note the default here is True, unlike the billing
#: flags, so an absent key means enabled.
BOOL_KEYS = frozenset({"booking_waitlist_enabled"})


def validate_booking_rules(features: dict) -> dict:
    validate_int_rules(features, INT_RULES)
    return validate_bool_keys(features, BOOL_KEYS)


def int_rule(features: dict, key: str) -> int:
    return _int_rule(features, key, INT_RULES)
