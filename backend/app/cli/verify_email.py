"""Mark a user's email address as confirmed, from the host.

Sign-in requires a confirmed address. That closes a real hole — otherwise anyone
could register with a mailbox they do not own and hold a session on it — but it
also means an account that never confirmed cannot get in, and the only
self-service way back, ``/resend-verification``, needs a working mail transport.

Email is the component that fails quietly here: sends are dispatched through
Celery and the dispatch sites swallow failures, so an instance can accumulate
unconfirmed accounts without anyone noticing until they try to sign in. Without
this command the remedy is raw SQL against the production database, which is a
worse thing to put in a support answer than one documented command.

Deliberately does not send anything. It is for the case where sending is what is
broken; the operator has confirmed who the person is by some other means.

Usage:
    python -m app.cli.verify_email --email someone@example.org
    python -m app.cli.verify_email --all-unverified --yes
    python -m app.cli.verify_email --list
"""

import argparse
import sys
from datetime import datetime, timezone

# Importing User alone is not enough: its relationships name classes defined in
# other modules, and SQLAlchemy cannot configure the mapper until all of them are
# registered. Standalone, that surfaces as "expression 'Person' failed to locate
# a name" the first time a query runs — which the test suite never sees, because
# its conftest has already imported everything.
import app.db.models_registry  # noqa: F401
from app.db.session import SessionLocal
from app.domains.auth.models import User


def _unverified(db):
    return (
        db.query(User)
        .filter(User.email_verified.is_(False) | User.email_verified.is_(None))
        .order_by(User.email)
        .all()
    )


def _confirm(user: User) -> None:
    user.email_verified = True
    user.email_verified_at = datetime.now(timezone.utc)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli.verify_email",
        description=(
            "Mark an email address as confirmed so its owner can sign in. For "
            "when the mail transport is what is broken."
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--email", help="The address to confirm.")
    group.add_argument(
        "--list",
        action="store_true",
        help="Show every account with an unconfirmed address and exit.",
    )
    group.add_argument(
        "--all-unverified",
        action="store_true",
        help=(
            "Confirm every unconfirmed address. Needs --yes. Use after fixing a "
            "mail transport that had been failing silently."
        ),
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt. Required with --all-unverified.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.list:
            pending = _unverified(db)
            if not pending:
                print("Every account has a confirmed address.")
                return
            print(f"{len(pending)} account(s) with an unconfirmed address:\n")
            for u in pending:
                print(f"  {u.email}")
            print("\nConfirm one with --email, or all of them with "
                  "--all-unverified --yes.")
            return

        if args.all_unverified:
            pending = _unverified(db)
            if not pending:
                print("Every account has a confirmed address. Nothing to do.")
                return
            if not args.yes:
                print(
                    f"This would confirm {len(pending)} address(es) without any of "
                    "them proving they own the mailbox.\n"
                    "Re-run with --yes if that is what you mean.",
                    file=sys.stderr,
                )
                sys.exit(1)
            for u in pending:
                _confirm(u)
            db.commit()
            print(f"Confirmed {len(pending)} address(es).")
            return

        user = db.query(User).filter(User.email == args.email).first()
        if not user:
            print(f"No account with the address {args.email}.", file=sys.stderr)
            sys.exit(1)
        if user.email_verified:
            print(f"{args.email} is already confirmed. Nothing to do.")
            return

        _confirm(user)
        db.commit()
        print(f"Confirmed {args.email}. They can sign in now.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
