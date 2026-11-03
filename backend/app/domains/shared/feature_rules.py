"""Validating what an organization configures in ``features``.

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

The key names are checked too, against the canonical set assembled in
``domains/organizations/feature_keys.py``, and that half is save-side only: the
endpoint merges after the schema runs, so a stray key stored before the check
existed is never re-validated. See ``validate_known_keys``.
"""

from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.core.schema_types import Email

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


def validate_known_keys(features: dict, keys: frozenset[str]) -> dict:
    """Refuse a key the product does not define, leaving stored strays alone.

    The counterpart of the value checks above, and the reason those were not
    enough on their own: ``PUT /settings/`` merges sparsely, so a key nothing
    recognises is written and then kept forever (#494). A typo in a flag name
    answers 200, configures nothing, and leaves no record of why.

    The rule is **"an unknown key is refused", never "all known keys are
    required"**. A fresh install stores a subset of the set and the rest resolve
    through their read-side defaults, so absence is legitimate and must stay
    legitimate.

    This validates the request body, not the row. The merge in
    ``api/v1/endpoints/settings.py`` runs *after* the schema, so only the keys a
    request actually carries reach here and a stray already in ``features`` is
    never re-validated. That is deliberate: an instance holding one can still
    save an unrelated flag, and dropping it would mean deleting data nobody has
    surveyed for no gain this refusal does not already provide.
    """
    unknown = sorted(set(features) - keys)
    if unknown:
        raise ValueError(f"unrecognised feature keys: {', '.join(unknown)}")
    return features


_EMAIL = TypeAdapter(Email)


def validate_email_keys(features: dict, keys: frozenset[str]) -> dict:
    """Validate and normalise an address stored in ``features``.

    ``features`` bypasses the schema types entirely, so an address living in it
    gets none of the checks every other address in the product receives (#495).
    This routes it through the same shared ``Email`` annotation rather than a
    second, looser rule: normalise first, then the anchored ASCII pattern.

    ``Email`` is ASCII-only because a login address is folded by both
    ``str.lower()`` and Postgres ``lower()`` and the two agree on little else
    (#242). No key here has a uniqueness index, so none of them needs that
    restriction, but reuse is cheaper than a second address rule that would be
    free to disagree with the first.

    Unset stays unset. ``None`` and ``""`` are left alone, because every read is
    guarded by truthiness and both already mean "send no notification"; an admin
    clearing the field must not be refused.

    The normalised value is written back, so what is stored is what the mail
    transport will be handed.
    """
    for key in sorted(keys):
        if key in features and features[key] not in (None, ""):
            try:
                features[key] = _EMAIL.validate_python(features[key])
            except ValidationError as exc:
                raise ValueError(f"{key} must be a valid email address") from exc
    return features
