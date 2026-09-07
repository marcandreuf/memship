"""The default-membership-type migration, run for real against a throwaway database.

The rest of the suite builds its schema with ``create_all`` and never invokes
alembic, so nothing else would notice if the back-fill regressed on an install
that upgrades rather than starts fresh — and the install that matters most is
the one with no free tier at all, which is every club our own seed created.
"""

import os

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.core.config import settings

BEFORE = "a4b5c6d7e8f9"
DEFAULT_TIER = "a5b6c7d8e9f0"

BASE_URL = os.getenv("DATABASE_TEST_URL", settings.DATABASE_TEST_URL)
_WORKER = os.getenv("PYTEST_XDIST_WORKER", "master")


def _server_url() -> str:
    return BASE_URL.rsplit("/", 1)[0] + "/postgres"


def _url(database: str) -> str:
    return BASE_URL.rsplit("/", 1)[0] + f"/{database}"


def _alembic_at(database: str, revision: str) -> None:
    """Migrate the scratch database, not whatever ``DATABASE_URL`` points at.

    ``alembic/env.py`` overrides the URL on the ``Config`` object with
    ``DATABASE_URL`` whenever it is set, and CI sets it for the whole
    integration step — so the environment has to be pointed at the scratch
    database too, or this runs DDL against the shared test database.
    """
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", _url(database))
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = _url(database)
    try:
        command.upgrade(cfg, revision)
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


def _install(name: str, pre_state: str):
    """A database migrated to just before the default tier, seeded, then upgraded.

    Suffixed per xdist worker so parallel workers don't race DROP/CREATE
    DATABASE against the same scratch database.
    """
    database = f"memship_{name}_migration_test_{_WORKER}"
    admin = sa.create_engine(_server_url(), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'))
            conn.execute(sa.text(f'CREATE DATABASE "{database}"'))
    except sa.exc.OperationalError as exc:
        admin.dispose()
        pytest.skip(f"no database server for the migration test: {exc}")

    _alembic_at(database, BEFORE)
    engine = sa.create_engine(_url(database))
    with engine.begin() as conn:
        conn.execute(sa.text(pre_state))
    _alembic_at(database, DEFAULT_TIER)

    yield engine

    engine.dispose()
    with admin.connect() as conn:
        conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'))
    admin.dispose()


PAID_ONLY = """
    INSERT INTO membership_types (name, slug, base_price, billing_frequency,
                                  display_order, is_active)
    VALUES ('Full Member', 'full-member', 50.00, 'monthly', 1, true),
           ('Student', 'student', 25.00, 'monthly', 2, true);

    INSERT INTO persons (first_name, last_name, email)
    VALUES ('Billed', 'ByAccident', 'billed@migration.test');

    INSERT INTO members (person_id, membership_type_id, member_number, status, joined_at)
    SELECT p.id, m.id, 'M-0001', 'active', current_date
    FROM persons p, membership_types m
    WHERE p.email = 'billed@migration.test' AND m.slug = 'full-member';
"""

WITH_FREE_TIERS = """
    INSERT INTO membership_types (name, slug, base_price, billing_frequency,
                                  display_order, is_active)
    VALUES ('Full Member', 'full-member', 50.00, 'monthly', 1, true),
           ('Retired Free', 'retired-free', 0, 'annual', 1, false),
           ('Honorary', 'honorary', 0, 'one_time', 2, true);
"""


@pytest.fixture(scope="module")
def no_free_tier():
    yield from _install("default_tier_created", PAID_ONLY)


@pytest.fixture(scope="module")
def free_tier_present():
    yield from _install("default_tier_promoted", WITH_FREE_TIERS)


def _defaults(engine) -> list[tuple]:
    with engine.connect() as conn:
        return conn.execute(
            sa.text(
                "SELECT slug, base_price, is_active FROM membership_types "
                "WHERE is_default"
            )
        ).all()


class TestInstallWithNoFreeTier:
    """Our own seed, and any club that created its paid plans first."""

    def test_a_free_default_is_created(self, no_free_tier):
        assert _defaults(no_free_tier) == [("registered", 0, True)]

    def test_the_paid_plans_are_left_as_they_are(self, no_free_tier):
        with no_free_tier.connect() as conn:
            paid = conn.execute(
                sa.text(
                    "SELECT count(*) FROM membership_types WHERE base_price > 0"
                )
            ).scalar_one()

        assert paid == 2

    def test_no_member_is_moved(self, no_free_tier):
        """Cleaning up members the bug already parked on a paid plan is a
        decision for an admin, not for a migration."""
        with no_free_tier.connect() as conn:
            slug = conn.execute(
                sa.text(
                    "SELECT t.slug FROM members m "
                    "JOIN membership_types t ON t.id = m.membership_type_id "
                    "JOIN persons p ON p.id = m.person_id "
                    "WHERE p.email = 'billed@migration.test'"
                )
            ).scalar_one()

        assert slug == "full-member"


class TestInstallWithFreeTiers:
    def test_the_active_free_tier_wins(self, free_tier_present):
        """Two free tiers must resolve the same way on every copy of the same
        database, and a hidden one is not somewhere to send new sign-ups."""
        assert _defaults(free_tier_present) == [("honorary", 0, True)]

    def test_nothing_is_invented(self, free_tier_present):
        with free_tier_present.connect() as conn:
            count = conn.execute(
                sa.text("SELECT count(*) FROM membership_types")
            ).scalar_one()

        assert count == 3
