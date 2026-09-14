"""Password hashing and verification using argon2."""

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

ph = PasswordHasher()


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False


_decoy: tuple[PasswordHasher, str] | None = None


def decoy_hash() -> str:
    """A hash of a secret nobody holds, so nothing can ever verify against it.

    Built from whichever hasher is current, and rebuilt if that hasher is
    replaced. Freezing one at import looks cheaper and is wrong: the decoy's
    only job is to cost what a real verification costs, and a decoy left behind
    by a previous ``ph`` costs something else entirely. The integration suite
    swaps in far cheaper parameters, so this is not hypothetical.
    """
    global _decoy
    if _decoy is None or _decoy[0] is not ph:
        _decoy = (ph, ph.hash(secrets.token_urlsafe(32)))
    return _decoy[1]


def spend_verify_work(password: str) -> None:
    """Spend what a real verification costs, and learn nothing from it.

    argon2 is slow on purpose, so an endpoint that skips it on one path and not
    on another answers faster for one kind of address than the other — the same
    disclosure as saying so outright, read off a clock instead of a response
    body (#102). Callers that return early use this to keep both paths level.
    """
    try:
        ph.verify(decoy_hash(), password)
    except VerificationError:
        pass


# Built at import, not left to the first caller. Building it costs one hash, and
# left lazy that cost lands on whichever request first takes a short-circuiting
# path — putting it on the branch that has to blend in, and only there. Doing it
# here moves it to startup, where it is nobody's measurement.
#
# It is a small share of a cold process's first response either way: on the dev
# container the first request costs ~210ms against ~70ms steady-state whichever
# address it carries, so most of that is the framework warming up, not this.
# Which is the point — a cost every first request pays discloses nothing, and a
# cost only one branch pays does.
#
# `decoy_hash` still rebuilds if `ph` is replaced.
decoy_hash()
