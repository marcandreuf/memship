"""The booking rules an organization configures in ``features``.

``features`` is free-form JSON, so these keys are checked twice: on the way in,
where an invalid value is refused, and on the way out, where a value stored
before the check existed falls back to its default instead of failing every
availability, booking and cancellation request with a 500.
"""

from typing import Any

#: key -> (default, minimum, maximum). The maximum keeps ``timedelta`` from
#: overflowing on an absurd value.
INT_RULES: dict[str, tuple[int, int, int]] = {
    "booking_window_days": (14, 1, 365),
    "booking_cancellation_deadline_hours": (24, 0, 8760),
}


def _is_valid(value: Any, minimum: int, maximum: int) -> bool:
    # bool is an int subclass; `true` is not a number of days.
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and minimum <= value <= maximum
    )


def validate_booking_rules(features: dict) -> dict:
    for key, (_, minimum, maximum) in INT_RULES.items():
        if key in features and not _is_valid(features[key], minimum, maximum):
            raise ValueError(
                f"{key} must be an integer between {minimum} and {maximum}"
            )
    return features


def int_rule(features: dict, key: str) -> int:
    default, minimum, maximum = INT_RULES[key]
    value = features.get(key, default)
    return value if _is_valid(value, minimum, maximum) else default
