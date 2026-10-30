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
has one. A registry is a second place to forget.

**Only pending migrations are consulted.** This module used to run every check
it could find against every database, on the reasoning that a check for an
applied revision passes by construction and that skipping it was not worth the
`alembic_version` bookkeeping. It named its own condition for revisiting that:
a check that would fail against a database its migration already upgraded.
`f5a6b7c8d9e0`'s check reads `members.user_id`, `29a3872dad10` drops it, and
the check did not pass by construction, it raised, which took the whole gate
down and refused every upgrade from 3.0.0 (memship#476).

The range is resolved with alembic's own revision walker, not by reading
`down_revision`: the tree holds a merge revision carrying two parents, and
following one of them drops a whole leg of the graph along with every check on
it.
"""

import importlib.util
import sys
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.script.revision import RevisionError

from app.core.config import settings

ALEMBIC_DIR = Path(__file__).resolve().parents[2] / "alembic"


def _load_check(path: Path) -> object | None:
    """``preflight_check`` from one migration file, or None.

    Loaded by path rather than imported as a package: `alembic/versions` is not
    one, and the files are historical records that must not start depending on
    application code to stay loadable.
    """
    spec = importlib.util.spec_from_file_location(f"_preflight_{path.stem}", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    check = getattr(module, "preflight_check", None)
    return check if callable(check) else None


def _script() -> ScriptDirectory:
    return ScriptDirectory(str(ALEMBIC_DIR))


def _pending(script: ScriptDirectory, current, target: str) -> list[str]:
    """The walk itself, taking the script directory so one call builds it once."""
    lower = current or None
    if isinstance(lower, (tuple, list)):
        lower = tuple(lower) or None

    applied = set()
    if lower is not None:
        applied = {lower} if isinstance(lower, str) else set(lower)

    try:
        walked = list(script.iterate_revisions(target, lower))
    except RevisionError:
        # The target is not ahead of the database, which is what a downgrade
        # looks like from here. No upgrade migration is pending, so there is
        # nothing for a precondition to refuse. Whether a downgrade *should* be
        # gated is a separate question; `scripts/upgrade.sh` guards that one
        # with --allow-downgrade.
        return []

    revisions = [
        script_rev.revision
        for script_rev in walked
        # iterate_revisions includes the lower bound; the pending range does
        # not, since that revision is the one already applied.
        if script_rev.revision not in applied
    ]
    return list(reversed(revisions))


def pending_revisions(current, target: str = "head") -> list[str]:
    """Revision ids in ``(current, target]``, oldest first.

    ``current`` is whatever the database reports, so a string, a tuple of heads
    or None; None means "from the base", alembic's own convention for a lower
    bound. The walk goes through ``iterate_revisions`` so that the merge
    revision in this tree resolves to both of its parents.
    """
    return _pending(_script(), current, target)


def pending_checks(current, target: str = "head") -> list[tuple[str, object]]:
    """The checks declared by the migrations this upgrade would apply.

    Empty when the database reports no revision at all. That is an unmigrated
    database: no data exists, so no data precondition can be violated, and
    every check would query tables that are not there yet. `scripts/upgrade.sh`
    skips the gate in that case anyway, so this is the defensive half.
    """
    if not current:
        return []

    script = _script()
    found = []
    for revision in _pending(script, current, target):
        check = _load_check(Path(script.get_revision(revision).path))
        if check is not None:
            found.append((revision, check))
    return found


def _summary(pending: list[str], checks: list[tuple[str, object]]) -> str:
    """What was examined, in the terms of the upgrade actually being attempted.

    The old wording, "N run, nothing blocking", counted every check in the
    repository's history. For the 3.0.0 upgrade that read as a pass over eight
    migrations while describing two that were already applied. Saying how many
    are pending and how many of those declared anything makes a silent gate
    visibly silent (memship-context#80).
    """
    if not pending:
        return "Pre-upgrade checks: nothing pending, the database is at the target."
    noun = "migration" if len(pending) == 1 else "migrations"
    if not checks:
        return (
            f"Pre-upgrade checks: {len(pending)} {noun} pending, "
            "none of which declares a data precondition."
        )
    return (
        f"Pre-upgrade checks: {len(pending)} {noun} pending, "
        f"{len(checks)} declared a check, nothing blocking."
    )


def main() -> int:
    engine = None
    try:
        engine = sa.create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            # The target is this image's own head: `scripts/upgrade.sh` runs
            # this module from the release being installed, against the
            # database the old one is still serving.
            current = MigrationContext.configure(conn).get_current_heads()
            pending = pending_revisions(current, "head") if current else []
            checks = pending_checks(current, "head")
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
        print(_summary(pending, checks))
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
