"""Running alembic must not switch the application's loggers off.

`alembic/env.py` configures logging from `alembic.ini` through
`logging.config.fileConfig`, whose `disable_existing_loggers` **defaults to
True**. That default sets `.disabled = True` on every logger not named in the
ini file, which is every `app.*` logger, for the remaining life of the process.

That was memship#506. `command.upgrade()` in one test silenced
`app.core.security.rate_limit`, and the two tests asserting that the Redis
fallback and its recovery are logged then found no records. The signature was
confusing in a way worth recording: they passed 32/32 alone, failed exactly two
after any alembic-invoking test, and passed in CI, because CI runs unit tests as
their own job that never touches alembic. It read like flakiness and was fully
deterministic.

This test pins the invariant rather than the symptom. Asserting on the rate-limit
tests would only have caught the one logger that happened to be asserted on; the
defect silenced all of them, including in any process that runs a migration
alongside the app.
"""

import logging
import os

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.core.config import settings

BASE_URL = os.getenv("DATABASE_TEST_URL", settings.DATABASE_TEST_URL)
_WORKER = os.getenv("PYTEST_XDIST_WORKER", "master")
SCRATCH = f"memship_alembic_logging_test_{_WORKER}"

# Loggers that must survive. One on the path the original defect broke, one
# chosen to show the blast radius was never specific to it.
APP_LOGGERS = (
    "app.core.security.rate_limit",
    "app.domains.billing.service",
)


def _server_url() -> str:
    return BASE_URL.rsplit("/", 1)[0] + "/postgres"


def _scratch_url() -> str:
    return BASE_URL.rsplit("/", 1)[0] + f"/{SCRATCH}"


@pytest.fixture
def scratch_db():
    """An empty database, so `command.current` runs `env.py` and reports nothing.

    The cheapest alembic command that actually executes `env.py`: the logging
    call under test happens at import of that module, so no migration needs to
    run for the damage to be done.
    """
    admin = sa.create_engine(_server_url(), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{SCRATCH}" WITH (FORCE)'))
            conn.execute(sa.text(f'CREATE DATABASE "{SCRATCH}"'))
    except sa.exc.OperationalError as exc:
        pytest.skip(f"no database server for the alembic logging test: {exc}")
    try:
        yield
    finally:
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{SCRATCH}" WITH (FORCE)'))
        admin.dispose()


def _run_alembic() -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", _scratch_url())
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = _scratch_url()
    try:
        command.current(cfg)
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


class TestAlembicLeavesAppLoggingAlone:
    def test_app_loggers_are_still_enabled_afterwards(self, scratch_db):
        for name in APP_LOGGERS:
            assert not logging.getLogger(name).disabled, f"{name} disabled before"

        _run_alembic()

        for name in APP_LOGGERS:
            assert not logging.getLogger(name).disabled, (
                f"{name} was disabled by running alembic. alembic/env.py must pass"
                " disable_existing_loggers=False to fileConfig (memship#506)."
            )

    def test_an_app_logger_still_emits_afterwards(self, scratch_db):
        """`disabled` is the mechanism, but a record arriving is what matters,
        and it is what the original failures actually asserted on.

        The handler is attached **after** alembic has run, deliberately, and not
        through `caplog`. `fileConfig` also replaces the root logger's handlers,
        so a `caplog` handler installed before the call is dropped by it and the
        assertion would fail for a reason that has nothing to do with #506. That
        is not a defect: pytest installs its handler per test, so the real tests
        get a fresh one after any earlier test ran a migration. Reproducing that
        ordering here keeps the test about the invariant.
        """
        _run_alembic()

        seen: list[str] = []

        class _Collect(logging.Handler):
            def emit(self, record):
                seen.append(record.getMessage())

        logger = logging.getLogger(APP_LOGGERS[0])
        handler = _Collect(level=logging.ERROR)
        logger.addHandler(handler)
        try:
            logger.error("probe after alembic")
        finally:
            logger.removeHandler(handler)

        assert "probe after alembic" in seen
