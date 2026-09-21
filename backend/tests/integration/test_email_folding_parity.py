"""The application and the database fold an address the same way (#242).

``normalize_email`` lower-cases with ``str.lower()``; the ``uq_users_email_lower``
index and the ``f5a6b7c8d9e0`` migration lower-case with Postgres ``lower()``.
The index only guarantees one account per address if both sides mean the same
thing by "lower". They do for ASCII and not in general, so the ``Email`` type
accepts ASCII only — and this pins the two against each other over everything
the type lets through, so they cannot drift apart again without a test going
red.
"""

from pydantic import BaseModel
from sqlalchemy import text

from app.core.schema_types import Email, normalize_email


class Model(BaseModel):
    email: Email


# Every character the local part may contain: printable ASCII less `@`.
ATOM = "".join(chr(c) for c in range(0x21, 0x7F) if chr(c) != "@")


def _pg_normalised(db, value: str) -> str:
    return db.execute(text("SELECT lower(btrim(:v))"), {"v": value}).scalar_one()


def test_every_accepted_character_folds_the_same_in_python_and_postgres(db):
    address = f"{ATOM}@Example.COM"
    accepted = Model(email=address).email
    assert accepted == normalize_email(address)
    assert accepted == _pg_normalised(db, address)


def test_what_the_application_stores_is_a_fixed_point_of_the_index(db):
    """The index folds the stored value; the application stores the folded
    value. The invariant needs the second folding to change nothing."""
    for raw in [
        f"{ATOM}@Example.COM",
        "  Marc.Andreu@Example.com  ",
        "\tADMIN@MEMSHIP.TEST\n",
        "a+b_c-d.e@Sub.Example.co.uk",
    ]:
        stored = Model(email=raw).email
        assert _pg_normalised(db, stored) == stored, raw


def test_space_padding_and_case_fold_the_same_from_raw(db):
    """The migration folded rows that were written before the application
    normalised, so on raw input the two should agree too. They do for spaces;
    ``btrim`` strips spaces only where ``str.strip`` strips every whitespace,
    so a tab- or newline-padded legacy row would come out of the migration
    still padded. No path in the application has ever written one, which is
    why that is recorded here rather than fixed."""
    for raw in [
        "  Marc.Andreu@Example.com  ",
        "a+b_c-d.e@Sub.Example.co.uk",
        "already@lower.case",
    ]:
        assert Model(email=raw).email == _pg_normalised(db, raw), raw


def test_the_divergence_the_restriction_exists_for(db):
    """Recorded, not just asserted away: the address the type now refuses is
    one the two foldings disagree on. If Postgres ever folds it the way Python
    does, the restriction could be revisited."""
    raw = "İREM@example.com"
    assert normalize_email(raw) != _pg_normalised(db, raw)
    assert len(normalize_email(raw)) == 17
    assert len(_pg_normalised(db, raw)) == 16
