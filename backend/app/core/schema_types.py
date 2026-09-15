"""Shared Pydantic field types.

One definition per concern, imported by the domain schema modules rather than
copied into each. ``Email`` was three identical copies; normalising one of them
would have left the other two writing un-normalised addresses to the same
columns.
"""

from typing import Annotated, Any

from pydantic import BeforeValidator, StringConstraints


def normalize_email(value: Any) -> Any:
    """Strip and lower-case an address, leaving anything else alone.

    Addresses are compared as opaque strings throughout — login, password
    reset, the taken-address check on signup, SSO account linking — so one
    capital resolves to no account at all and locks a member out of both
    sign-in and recovery, with no way back without an admin (#191).

    The rule lives in a function rather than in ``StringConstraints`` because
    the paths that never see a request body need it too: ``OAuthProfile``
    arrives from a provider as a plain dataclass, and the CLI builds addresses
    from its arguments.

    A non-string is returned untouched so the surrounding str schema can
    reject it as a type error rather than this raising ``AttributeError``.
    """
    if isinstance(value, str):
        return value.strip().lower()
    return value


# A simple regex rather than EmailStr, so dev domains (.test, .local) validate.
# The normalisation runs first, so a padded or upper-case address is corrected
# rather than rejected by the anchored pattern.
Email = Annotated[
    str,
    BeforeValidator(normalize_email),
    StringConstraints(
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        max_length=255,
    ),
]
