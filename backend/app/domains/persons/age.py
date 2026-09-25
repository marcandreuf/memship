"""A person's age, and whether it fits an age restriction."""

from datetime import date


def age_on(date_of_birth: date, reference: date) -> int:
    """Whole years completed on ``reference``."""
    age = reference.year - date_of_birth.year
    if (reference.month, reference.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1
    return age


def age_restriction_problem(
    date_of_birth: date | None,
    min_age: int | None,
    max_age: int | None,
    reference: date,
) -> str | None:
    """Why this birth date does not satisfy the restriction, or None if it does.

    An unknown birth date does not pass a stated restriction: waiving the limit
    because the club lacks the data is how an adult got into a youth camp
    (#291). Returns ``"birth_date_required"``, ``"below_min_age"`` or
    ``"above_max_age"``.
    """
    if min_age is None and max_age is None:
        return None
    if date_of_birth is None:
        return "birth_date_required"
    age = age_on(date_of_birth, reference)
    if min_age is not None and age < min_age:
        return "below_min_age"
    if max_age is not None and age > max_age:
        return "above_max_age"
    return None
