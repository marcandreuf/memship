"""`seed --test` run the way the e2e workflow runs it — the CLI as a subprocess.

`--test --reset-club-data` used to accept the reset flag and drop it: the
`--test` branch of `main()` never reached the only code that read it, so the
command reported success and handed the old dataset back (#460). That is the
command a developer reaches for when the suite fails on aged fixtures (#461),
so it is asserted through the real entry point rather than its helpers.

The database is a throwaway of its own: the fixed test accounts this seeds
would collide with the assertions in `test_cli_install_path.py`.
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
SCRATCH = f"memship_cli_test_mode_test_{_WORKER}"

ACTIVITY = "Chess Club Tournament"


def _server_url() -> str:
    return BASE_URL.rsplit("/", 1)[0] + "/postgres"


def _scratch_url() -> str:
    return BASE_URL.rsplit("/", 1)[0] + f"/{SCRATCH}"


@pytest.fixture(scope="module")
def scratch_db():
    admin = sa.create_engine(_server_url(), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{SCRATCH}" WITH (FORCE)'))
            conn.execute(sa.text(f'CREATE DATABASE "{SCRATCH}"'))
    except sa.exc.OperationalError as exc:
        pytest.skip(f"no database server for the test-mode seed test: {exc}")

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", _scratch_url())
    previous = os.environ.get("DATABASE_URL")
    # `alembic/env.py` overrides the configured URL from the environment.
    os.environ["DATABASE_URL"] = _scratch_url()
    try:
        command.upgrade(cfg, "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous

    engine = sa.create_engine(_scratch_url())
    yield engine

    engine.dispose()
    with admin.connect() as conn:
        conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{SCRATCH}" WITH (FORCE)'))
    admin.dispose()


def _seed(*args):
    env = {**os.environ, "DATABASE_URL": _scratch_url(), "APP_ENV": "development"}
    return subprocess.run(
        [sys.executable, "-m", "app.cli.seed", "--test", *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )


def _activity(engine):
    with engine.connect() as conn:
        return conn.execute(
            sa.text(
                "SELECT id, registration_ends_at > now() AS open "
                "FROM activities WHERE name = :n"
            ),
            {"n": ACTIVITY},
        ).one()


class TestResetClubData:
    def test_it_rebuilds_an_aged_dataset(self, scratch_db):
        first = _seed()
        assert first.returncode == 0, first.stdout + first.stderr

        # What a few weeks do to the dataset: the relative window closes.
        with scratch_db.begin() as conn:
            conn.execute(
                sa.text(
                    "UPDATE activities SET registration_ends_at = now() - interval '1 day' "
                    "WHERE name = :n"
                ),
                {"n": ACTIVITY},
            )
        aged = _activity(scratch_db)
        assert not aged.open

        result = _seed("--reset-club-data")

        assert result.returncode == 0, result.stdout + result.stderr
        assert "Resetting club data..." in result.stdout
        fresh = _activity(scratch_db)
        assert fresh.id != aged.id
        assert fresh.open


class TestFlagsItWouldIgnore:
    @pytest.mark.parametrize(
        "args, flag",
        [
            (["--demo"], "--demo"),
            (["--club-name", "Somewhere"], "--club-name"),
            (["--admin-email", "someone@example.org"], "--admin-email"),
        ],
    )
    def test_it_refuses_rather_than_dropping_them(self, scratch_db, args, flag):
        result = _seed(*args)

        assert result.returncode != 0
        assert f"--test cannot be combined with {flag}" in result.stderr
