"""The pre-upgrade check, run the way `scripts/upgrade.sh` runs it.

`f5a6b7c8d9e0` refuses an upgrade when two accounts hold one address in
different cases. The refusal is correct; running it only after the stack had
been replaced was not, because that turns a data problem into downtime (#194).

These tests hold a throwaway database at `e2f3a4b5c6d7` — the revision *before*
that migration — because once it has run, `uq_users_email_lower` makes the
duplicate impossible to create. That is the whole point of the index, and it is
also why a check for an applied revision passes by construction.

The CLI is driven as a real subprocess, like `test_cli_install_path.py`: the
exit code is what `upgrade.sh` branches on, so asserting it in-process would
test something the operator never runs.
"""

import os
import subprocess
import sys

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.core.config import settings

BASE_URL = os.getenv("DATABASE_TEST_URL", settings.DATABASE_TEST_URL)
_WORKER = os.getenv("PYTEST_XDIST_WORKER", "master")
SCRATCH = f"memship_preflight_test_{_WORKER}"

# The revision immediately before the one that can refuse.
BEFORE_THE_GUARD = "e2f3a4b5c6d7"


def _server_url() -> str:
    return BASE_URL.rsplit("/", 1)[0] + "/postgres"


def _scratch_url() -> str:
    return BASE_URL.rsplit("/", 1)[0] + f"/{SCRATCH}"


def _migrate_to(revision: str) -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", _scratch_url())
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = _scratch_url()
    try:
        command.upgrade(cfg, revision)
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


@pytest.fixture
def pre_guard_db():
    """A database one revision short of the guard, so duplicates are possible."""
    admin = sa.create_engine(_server_url(), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{SCRATCH}" WITH (FORCE)'))
            conn.execute(sa.text(f'CREATE DATABASE "{SCRATCH}"'))
    except sa.exc.OperationalError as exc:
        pytest.skip(f"no database server for the preflight test: {exc}")

    _migrate_to(BEFORE_THE_GUARD)
    engine = sa.create_engine(_scratch_url())
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{SCRATCH}" WITH (FORCE)'))
        admin.dispose()


def _preflight(url=None):
    env = {**os.environ, "DATABASE_URL": url or _scratch_url()}
    return subprocess.run(
        [sys.executable, "-m", "app.cli.preflight"],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


def _add_user(engine, email, name="Case"):
    with engine.begin() as conn:
        person_id = conn.execute(
            sa.text(
                "INSERT INTO persons (first_name, last_name, email) "
                "VALUES (:n, 'Clash', :e) RETURNING id"
            ),
            {"n": name, "e": email},
        ).scalar_one()
        conn.execute(
            sa.text(
                "INSERT INTO users (person_id, email, password_hash, is_active) "
                "VALUES (:p, :e, 'x', true)"
            ),
            {"p": person_id, "e": email},
        )


class TestItAnswersBeforeAnythingIsReplaced:
    def test_clean_data_passes(self, pre_guard_db):
        _add_user(pre_guard_db, "only.one@example.org")

        result = _preflight()

        assert result.returncode == 0, result.stdout + result.stderr
        assert "nothing blocking" in result.stdout

    def test_a_case_duplicate_is_refused(self, pre_guard_db):
        _add_user(pre_guard_db, "clash@example.org", name="First")
        _add_user(pre_guard_db, "Clash@Example.ORG", name="Second")

        result = _preflight()

        assert result.returncode == 1, result.stdout + result.stderr
        assert "would be refused" in result.stdout
        assert "clash@example.org" in result.stdout

    def test_it_names_the_revision_that_would_refuse(self, pre_guard_db):
        """An operator has to know which migration to read about."""
        _add_user(pre_guard_db, "clash@example.org", name="First")
        _add_user(pre_guard_db, "Clash@Example.ORG", name="Second")

        assert "f5a6b7c8d9e0" in _preflight().stdout

    def test_it_says_the_instance_is_untouched(self, pre_guard_db):
        """The report is read by someone whose upgrade just stopped. Saying the
        instance is still running is the difference between a refusal and an
        outage."""
        _add_user(pre_guard_db, "clash@example.org", name="First")
        _add_user(pre_guard_db, "Clash@Example.ORG", name="Second")

        assert "still running" in _preflight().stdout

    def test_it_writes_nothing(self, pre_guard_db):
        """A check that mutates is not a check. The migration's own guard makes
        no writes before raising, and neither may this."""
        _add_user(pre_guard_db, "clash@example.org", name="First")
        _add_user(pre_guard_db, "Clash@Example.ORG", name="Second")
        with pre_guard_db.connect() as conn:
            before = conn.execute(
                sa.text("SELECT id, email FROM users ORDER BY id")
            ).all()
            revision_before = conn.execute(
                sa.text("SELECT version_num FROM alembic_version")
            ).scalar_one()

        _preflight()

        with pre_guard_db.connect() as conn:
            assert conn.execute(sa.text("SELECT id, email FROM users ORDER BY id")).all() == before
            assert (
                conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
                == revision_before
            )


class TestWhenItCannotLook:
    def test_an_unreachable_database_is_not_reported_as_clear(self):
        """Being unable to look is not the same as having looked, and the caller
        is about to replace a running instance. Distinct exit code so
        `upgrade.sh` can say which happened."""
        dead = BASE_URL.rsplit("/", 1)[0].replace("@", "@bad-host-") + "/nothing"

        result = _preflight(url=dead)

        assert result.returncode == 2
        assert "could not run" in result.stderr
