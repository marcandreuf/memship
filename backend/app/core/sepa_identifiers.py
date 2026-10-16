"""The SEPA identifiers memship validates — an IBAN and a creditor identifier.

These lived in `domains/billing/schemas.py`, where only a mandate could reach
them. The organisation's *own* IBAN is validated by the organisations domain,
so it was checked by shape alone while a member's IBAN got the check digits
too — one rule in two places, disagreeing (#393). A bad debtor IBAN costs one
member's collection; a bad creditor IBAN or creditor identifier appears in
every file memship generates, so the bank returns the whole batch.
"""

import re

from pydantic_core import PydanticCustomError

IBAN_PATTERN = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{4,30}$")

# Country, two check digits, a three-character Creditor Business Code, then the
# national identifier. The business code is the creditor's own — "ZZZ" is the
# conventional unused value — and the national identifier's shape varies by
# country, which is why only the frame is enforced here.
CREDITOR_ID_PATTERN = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{3}[A-Z0-9]{1,28}$")


def normalize_pasted_iban(value: object) -> object:
    """An IBAN as pasted, reduced to how it is stored.

    People copy an IBAN in groups of four from a statement or a PDF, and the
    grouping is presentation — the stored value is unbroken and upper-case.
    Runs before the rest, so a correctly typed IBAN is not refused over
    whitespace while the checks below stay strict about a stored value.
    """
    if isinstance(value, str):
        return re.sub(r"\s+", "", value).upper()
    return value


def mod_97_ok(value: str) -> bool:
    """The ISO 7064 mod-97 check an IBAN carries in positions 3-4.

    Move the first four characters to the end, replace each letter by its
    value in base 36 (A=10 ... Z=35), and the integer that spells is 1 mod 97.
    """
    rearranged = value[4:] + value[:4]
    return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1


def validate_iban_format(iban: str) -> bool:
    """IBAN structure *and* check digits.

    The check digits are the point: without them a typo in an account number is
    accepted, stored, and written into a pain.008 file — which the official
    schema also accepts, because its IBAN type is a bare pattern — so the bank
    is the first thing that notices, and it can return the whole batch.

    Strict about case and spacing: this validates an IBAN as stored, not as
    typed. `normalize_pasted_iban` is what turns one into the other.
    """
    if not IBAN_PATTERN.match(iban):
        return False
    return mod_97_ok(iban)


def blank_to_none(value: object) -> object:
    """An empty optional field, as the absence of a value.

    The settings screen drops empty fields from its payload, but an API caller
    clearing the organisation's IBAN by sending `""` used to be accepted when
    the field was a bare `max_length`. Mapping it to `None` keeps that door
    open without letting an empty string past the checks below — which is why
    this is a *settings* concern and not part of `refuse_invalid_iban`, whose
    other caller is a mandate field that must not become null.
    """
    if isinstance(value, str) and not value.strip():
        return None
    return value


def refuse_invalid_iban(value: str | None) -> str | None:
    """The field validator every IBAN field applies after normalisation.

    Lives on the schema so the rule is enforced at the boundary rather than
    only in the service — a pattern on the field and a checksum in the service
    is two rules disagreeing about what an IBAN is.

    Raises `PydanticCustomError` rather than `ValueError` so the 422 carries a
    stable `type` the locale files can key on. A bare `ValueError` reaches the
    administrator as `Value error, Invalid IBAN` — Pydantic's own prefix, in
    English, on a screen that may be running in Catalan (#377). The structural
    check is here too, not a `pattern=` on the field, because a pattern failure
    answers with the regex itself.

    Two codes, because the remedies differ: `malformed_iban` is not shaped like
    an account number at all, `invalid_iban` is shaped right but its check
    digits do not agree with the rest.
    """
    if value is None:
        return value
    if not IBAN_PATTERN.match(value):
        raise PydanticCustomError("malformed_iban", "Not an IBAN")
    if not mod_97_ok(value):
        raise PydanticCustomError("invalid_iban", "Invalid IBAN")
    return value


def refuse_invalid_creditor_id(value: str | None) -> str | None:
    """The organisation's SEPA creditor identifier, by structure.

    It was `max_length=35` and nothing else, so `not-a-creditor-id-at-all` was
    accepted and written into `CdtrSchmeId` in every file (#393).

    Only the frame is checked: country, two check digits, a three-character
    business code, and at least one character of national identifier. The
    mod-97 check digits are deliberately *not* enforced — the national
    identifier's composition varies by country, and a stored value that does
    not satisfy them must not lock an operator out of the settings screen that
    is the only place to correct it. That is a decision worth revisiting with a
    data migration beside it, not a stricter regex.
    """
    if value is None:
        return value
    if not CREDITOR_ID_PATTERN.match(value):
        raise PydanticCustomError("malformed_creditor_id", "Not a SEPA creditor identifier")
    return value
