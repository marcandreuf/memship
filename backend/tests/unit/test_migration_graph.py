"""Structural guards for the Alembic revision graph.

These run without a database. They exist because a broken revision graph does
not fail any other test — the integration suite builds its schema straight from
the models and never invokes Alembic — but it does stop the container from
booting: `entrypoint.sh` runs `alembic upgrade head` under `set -e`.

A duplicate revision id shipped once and made every deployment exit on start.
"""

import ast
import re
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_ROOT = Path(__file__).resolve().parents[2]
VERSIONS_DIR = BACKEND_ROOT / "alembic" / "versions"


def _literal(module: ast.Module, name: str):
    """Return the literal value assigned to a module-level name, or None."""
    for node in module.body:
        targets = (
            [node.target] if isinstance(node, ast.AnnAssign) else getattr(node, "targets", [])
        )
        for target in targets:
            if isinstance(target, ast.Name) and target.id == name and node.value is not None:
                try:
                    return ast.literal_eval(node.value)
                except ValueError:
                    return None
    return None


def _revision_files():
    return sorted(p for p in VERSIONS_DIR.glob("*.py") if p.name != "__init__.py")


def _parse(path: Path):
    module = ast.parse(path.read_text(), filename=str(path))
    return _literal(module, "revision"), _literal(module, "down_revision")


@pytest.fixture(scope="module")
def revisions():
    """Map revision id -> list of files declaring it (a list, to expose clashes)."""
    found: dict[str, list[Path]] = {}
    for path in _revision_files():
        revision, _ = _parse(path)
        assert revision, f"{path.name} declares no revision id"
        found.setdefault(revision, []).append(path)
    return found


def test_migration_files_exist():
    assert _revision_files(), "no Alembic revision files found"


def test_revision_ids_are_unique(revisions):
    """Two files sharing a revision id make Alembic raise CycleDetected.

    This is the exact defect that shipped in the mailing migration: the feature
    was committed twice and the second copy reused an id already taken by an
    older revision, so `alembic upgrade head` refused to run anything at all.
    """
    clashes = {
        revision: [p.name for p in paths]
        for revision, paths in revisions.items()
        if len(paths) > 1
    }
    assert not clashes, f"duplicate Alembic revision ids: {clashes}"


def test_down_revisions_resolve(revisions):
    """Every parent referenced by a migration must actually exist."""
    known = set(revisions)
    dangling = {}
    for path in _revision_files():
        revision, down = _parse(path)
        parents = down if isinstance(down, (tuple, list)) else [down]
        missing = [p for p in parents if p is not None and p not in known]
        if missing:
            dangling[path.name] = missing
    assert not dangling, f"migrations point at unknown parents: {dangling}"


def test_revision_id_matches_filename(revisions):
    """`alembic revision` names the file after the id; drift means a hand edit."""
    mismatched = {}
    for revision, paths in revisions.items():
        for path in paths:
            if not path.name.startswith(f"{revision}_"):
                mismatched[path.name] = revision
    assert not mismatched, f"filename does not match its revision id: {mismatched}"


def test_graph_loads_and_has_a_single_head():
    """Load the graph through Alembic itself and require exactly one head.

    Catches cycles and unmerged branches — both of which break startup even
    though every other test in the suite would still pass.
    """
    config = Config()
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    script = ScriptDirectory.from_config(config)

    revisions = list(script.walk_revisions())
    assert revisions, "Alembic loaded no revisions"

    heads = script.get_heads()
    assert len(heads) == 1, (
        f"expected a single head, found {len(heads)}: {heads}. "
        "Merge the branches with `alembic merge` before shipping."
    )


def test_no_stale_revision_ids_in_source():
    """A revision id must not linger in a file that no longer defines it.

    Cheap protection against the copy-paste that produced the duplicate: the
    second file kept the old id in its docstring header too.
    """
    known = {rev for rev, _ in (_parse(p) for p in _revision_files()) if rev}
    pattern = re.compile(r"Revision ID:\s*([0-9a-f]+)", re.IGNORECASE)
    wrong = {}
    for path in _revision_files():
        declared, _ = _parse(path)
        header = pattern.search(path.read_text())
        if header and header.group(1) != declared and header.group(1) in known:
            wrong[path.name] = (header.group(1), declared)
    assert not wrong, f"docstring Revision ID disagrees with the declared id: {wrong}"
