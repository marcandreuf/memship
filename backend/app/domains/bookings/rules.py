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
    # The club's default for how long before a slot a member's cancellation is
    # refundable. A space may set its own (#604).
    "booking_cancellation_deadline_minutes": (1440, 0, 525_600),
    # Pay-to-confirm bookings (#603). Separate from the activity values on
    # purpose: a court slot and an event are not paid on the same clock.
    # How long an unpaid booking may be held when auto-cancel is on.
    "booking_auto_cancel_hours": (24, 1, 8760),
    # How long before the slot starts a pending booking must be paid. 0 suits a
    # club that takes cash at the door and marks it paid before the start.
    "booking_payment_cutoff_minutes": (60, 0, 10080),
    # The shortest hold the club offers: a booking that would get less is
    # refused rather than created already doomed.
    "booking_min_hold_minutes": (15, 1, 1440),
    # The shortest hold for which a waitlister is promoted automatically. Below
    # it, every waitlister is told the seat is free and the first to book wins.
    "booking_auto_promotion_min_minutes": (120, 1, 10080),
}


#: Read as a boolean, through `bool(features.get(key, True))` in
#: `bookings/service.py`, so it cannot raise. The check refuses the string
#: `"false"`, which is truthy and would switch the waitlist on for an admin who
#: meant to switch it off. Note the waitlist defaults to True, unlike the billing
#: flags, so an absent key means enabled.
BOOL_KEYS = frozenset(
    {
        "booking_waitlist_enabled",
        # The club default for releasing an unpaid booking before its cut-off.
        # Read as `is True`, so unlike the waitlist an absent key means off.
        "booking_auto_cancel_enabled",
    }
)


#: The configuration keys this domain owns, for the canonical set in
#: ``domains/organizations/feature_keys.py`` (#494). The `bookings` module gate
#: is **not** here: it decides whether the module exists on this instance at
#: all rather than tuning a value, so it is grouped with the other gates there.
FEATURE_KEYS = frozenset(INT_RULES) | BOOL_KEYS


def validate_booking_rules(features: dict) -> dict:
    validate_int_rules(features, INT_RULES)
    return validate_bool_keys(features, BOOL_KEYS)


def int_rule(features: dict, key: str) -> int:
    return _int_rule(features, key, INT_RULES)
