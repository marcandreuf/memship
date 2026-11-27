"""Remove accounts nobody ever confirmed (#645).

An account whose address was never confirmed cannot sign in (``auth.py:147``),
cannot be approved (#643), and holds its address in ``users.email``, which is
unique. Nothing removed it, so every abandoned sign-up accumulated and kept that
address reserved against the person who may later want it.

**This is hygiene, not the fix.** A sweep leaves a window between runs in which
an unconfirmed row still holds an address, so it does not replace #644, which
resolves that collision at the moment somebody with a better claim arrives. What
it covers is the common case those two do not: nobody comes back for the address
at all.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.domains.auth.models import User
from app.domains.persons.service import (
    UnverifiedAccountHasHistory,
    discard_unverified_account,
)

logger = logging.getLogger(__name__)

# Well past ``VERIFICATION_TOKEN_TTL_HOURS`` (24h), because the token expiring is
# not the same as the person being gone: ``resend_verification`` issues a fresh
# one for as long as the account exists, so somebody can still finish days later.
# A month says nobody is coming back, and an unusable account costing a month of
# a reserved address is a far better failure than deleting one its owner was
# still returning to.
UNVERIFIED_GRACE_DAYS = 30


def purge_unverified_accounts(
    db: Session, *, grace_days: int = UNVERIFIED_GRACE_DAYS
) -> dict:
    """Delete every account left unconfirmed for longer than the grace period.

    Scoped to ``users`` rows, deliberately and load-bearingly. Verification state
    lives only on an account: a member an administrator entered by hand has no
    ``users`` row at all, so a sweep written over persons or members would match
    every one of them and delete the club. The query below is the whole safety
    argument, and it is why this takes no "unverified member" shortcut.

    ``email_verified`` is matched as false *or* null, following
    ``cli/verify_email.py``: the column has a default but rows predating it carry
    NULL, and ``!= True`` would skip them in SQL.

    Returns a summary for the task log. Accounts holding financial history are
    counted and skipped rather than raising, so one unexpected row cannot stop
    the run; that state should be unreachable since #643.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=grace_days)
    candidates = (
        db.query(User)
        .filter(
            (User.email_verified.is_(False)) | (User.email_verified.is_(None)),
            User.created_at < cutoff,
        )
        .all()
    )

    deleted, skipped = 0, 0
    for user in candidates:
        # Logged one by one and before the delete: the cascade reaches the
        # person, the member, contacts, addresses and bookings, and a scheduled
        # job that removes all of that silently is the worst shape this could
        # take. The audit row goes in alongside, written by the shared helper.
        try:
            discard_unverified_account(db, user)
        except UnverifiedAccountHasHistory:
            skipped += 1
            logger.warning(
                "Unverified account %s has financial history; left in place",
                user.email,
            )
            continue
        deleted += 1
        logger.info(
            "Deleted unverified account %s (party %s), unconfirmed since %s",
            user.email,
            user.party_id,
            user.created_at,
        )

    return {
        "deleted": deleted,
        "skipped_with_history": skipped,
        "grace_days": grace_days,
        "cutoff": cutoff.isoformat(),
    }
