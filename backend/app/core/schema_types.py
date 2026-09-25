"""Shared Pydantic field types.

One definition per concern, imported by the domain schema modules rather than
copied into each. ``Email`` was three identical copies; normalising one of them
would have left the other two writing un-normalised addresses to the same
columns.
"""

from typing import Annotated, Any

from pydantic import AfterValidator, BeforeValidator, StringConstraints


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
#
# ASCII only, on purpose. The address is folded twice — by ``str.lower()`` here
# and by Postgres ``lower()`` in the ``uq_users_email_lower`` index — and the
# two agree on every ASCII letter and on nothing else that can be relied on:
# ``İ`` (U+0130) becomes ``i`` plus a combining dot in Python and a bare ``i``
# in Postgres, so the same typed address could be stored twice under an index
# meant to forbid exactly that, and could never be signed in with (#242).
# Restricting what is accepted to what both fold identically is what makes the
# index and the application mean the same thing by "normalised". The visible
# ASCII range less ``@`` — ``!`` to ``?`` and ``A`` to ``~`` — is the previous
# ``[^@\s]`` with the non-ASCII half removed.
_ASCII_ATOM = r"[!-?A-~]+"

Email = Annotated[
    str,
    BeforeValidator(normalize_email),
    StringConstraints(
        pattern=rf"^{_ASCII_ATOM}@{_ASCII_ATOM}\.{_ASCII_ATOM}$",
        max_length=255,
    ),
]


def NonBlank(max_length: int):
    """A required text field: surrounding whitespace is stripped before the
    length check, so a value made only of spaces is refused like an empty one
    instead of being stored and rendered as a blank name (#285)."""
    return Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length),
    ]


def _require_content(value: str) -> str:
    if not value.strip():
        raise ValueError("String should not be blank")
    return value


def NonBlankText(max_length: int | None = None):
    """Required free text — a consent, an announcement body — that must say
    something but is stored as typed: leading indentation and trailing line
    breaks can be part of the text, so unlike ``NonBlank`` nothing is stripped."""
    return Annotated[
        str,
        StringConstraints(min_length=1, max_length=max_length),
        AfterValidator(_require_content),
    ]


def refuse_null(value: Any) -> Any:
    """For an update schema's optional field backed by a NOT NULL column:
    omitting it keeps the stored value, but an explicit ``null`` is refused
    rather than reaching the database. Validators only run on values the body
    actually carries, so omission is unaffected."""
    if value is None:
        raise ValueError("This field cannot be empty")
    return value
