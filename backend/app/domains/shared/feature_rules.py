"""Validating the integer values an organization configures in ``features``.

``features`` is free-form JSON on a single row, so a value there is checked
twice: on the way in, where an invalid one is refused, and on the way out, where
a value stored before the check existed falls back to its default rather than
raising from inside whatever reads it. ``domains/bookings/rules.py`` established
the pattern; this is the part both it and ``domains/billing/rules.py`` share, so
the two cannot drift into disagreeing about what "valid" means.

**Ranges are deliberately permissive.** The read-side fallback replaces a stored
value with a default, so a range tighter than what the code already honours would
silently change behaviour on an instance that had configured the edge. The bounds
here are wide enough that no value a real instance could plausibly hold changes
meaning; the fallback is for wrong types and absurd values, not for tightening
policy after the fact.
"""

from typing import Any

#: key -> (default, minimum, maximum)
IntRules = dict[str, tuple[int, int, int]]


def is_valid_int(value: Any, minimum: int, maximum: int) -> bool:
    # bool is an int subclass; `true` is not a number of days.
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and minimum <= value <= maximum
    )


def validate_int_rules(features: dict, rules: IntRules) -> dict:
    """Refuse an out-of-range or wrong-typed value, leaving an absent key alone.

    Absence is legitimate: every one of these keys has a default and a fresh
    install stores only some of them.
    """
    for key, (_, minimum, maximum) in rules.items():
        if key in features and not is_valid_int(features[key], minimum, maximum):
            raise ValueError(
                f"{key} must be an integer between {minimum} and {maximum}"
            )
    return features


def int_rule(features: dict, key: str, rules: IntRules) -> int:
    default, minimum, maximum = rules[key]
    value = features.get(key, default)
    return value if is_valid_int(value, minimum, maximum) else default

def validate_bool_keys(features: dict, keys: frozenset[str]) -> dict:
    """Refuse a non-boolean in a flag that is read as one.

    These reads never raise, so this is not crash protection. It is about a
    specific wrong answer: ``bool`` is total, so the string ``"false"`` is
    truthy and a flag an admin meant to switch off reads as on. Validating the
    type on the way in is what stops an instance reaching that state.

    Deliberately save-side only. A read-side fallback would have to reinterpret
    a value already stored, and that is the one change in this area that would
    alter a running instance's behaviour rather than preserve it.
    """
    for key in sorted(keys):
        if key in features and not isinstance(features[key], bool):
            raise ValueError(f"{key} must be true or false")
    return features
