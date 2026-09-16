"""Ask the pending migrations whether this upgrade would be refused.

A migration is allowed to refuse. `f5a6b7c8d9e0` does: it aborts when two
accounts hold the same address in different cases, because folding them picks a
winner between two people's logins, which is not a migration's decision.

The refusal is correct. Where it happened was not. Migrations are applied by the
API container on start, so the check ran *after* the old stack had been replaced
— the API crash-looped under `unless-stopped`, Caddy and the frontend stayed up
so members got errors rather than a maintenance page, and the instance stayed
down until a person decided which account to retire (#194).

This module runs the same checks from the new image against the still-running
old database, before anything is recreated. `scripts/upgrade.sh` calls it
between pulling the images and applying them.

    python -m app.cli.preflight

Exit codes: 0 nothing would refuse, 1 something would (report on stdout),
2 the checks could not be run at all.

**What a pass does and does not promise.** It promises that no migration's
declared data precondition is violated. It cannot promise the upgrade will
succeed — disk, lock timeouts and a bug in a migration are all outside what any
check here can see.

Checks live in the migration that would refuse, next to the refusal, and are
found by name rather than by a registry: a migration exposing `preflight_check`
has one. A registry is a second place to forget. Every check is run, including
those for revisions already applied — such a check passes by construction, since
its own migration enforced the condition, and one query costs less than the
`alembic_version` bookkeeping needed to skip it. Revisit that when a check
appears that would fail against a database its migration already upgraded.
"""

import importlib.util
import sys
from pathlib import Path

import sqlalchemy as sa

from app.core.config import settings

VERSIONS = Path(__file__).resolve().parents[2] / "alembic" / "versions"


def _checks() -> list[tuple[str, object]]:
    """Every migration exposing ``preflight_check``, in filename order.

    Loaded by path rather than imported as a package: `alembic/versions` is not
    one, and the files are historical records that must not start depending on
    application code to stay loadable.
    """
    found = []
    for path in sorted(VERSIONS.glob("*.py")):
        spec = importlib.util.spec_from_file_location(f"_preflight_{path.stem}", path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        check = getattr(module, "preflight_check", None)
        if callable(check):
            found.append((getattr(module, "revision", path.stem), check))
    return found


def main() -> int:
    checks = _checks()
    if not checks:
        print("Pre-upgrade checks: none to run.")
        return 0

    engine = None
    try:
        engine = sa.create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            blocks = [
                (revision, report)
                for revision, check in checks
                if (report := check(conn)) is not None
            ]
    except sa.exc.SQLAlchemyError as exc:
        # Deliberately not "no checks ran, carry on". Being unable to look is
        # not the same as having looked, and the caller is about to replace a
        # running instance.
        print(f"Pre-upgrade checks could not run: {exc}", file=sys.stderr)
        return 2
    finally:
        if engine is not None:
            engine.dispose()

    if not blocks:
        print(f"Pre-upgrade checks: {len(checks)} run, nothing blocking.")
        return 0

    print(f"\nThis upgrade would be refused by {len(blocks)} migration(s).\n")
    for revision, report in blocks:
        print(f"--- {revision} ---\n{report}\n")
    print(
        "Nothing has been changed and the instance is still running the "
        "version it was.\nResolve the above, then run the upgrade again.\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
