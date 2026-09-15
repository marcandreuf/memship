"""The members.user_id uniqueness migration, run for real against a throwaway
database (#187).

Mirrors ``test_default_tier_migration.py``: the rest of the suite builds its
schema with ``create_all`` and never invokes alembic, so nothing else would
notice if the back-fill picked the wrong row to keep on an install carrying
pre-existing duplicates.
"""

import os

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.core.config import settings

BEFORE = "f5a6b7c8d9e0"
UNIQUE_USER_ID = "c58bc5181d90"

BASE_URL = os.getenv("DATABASE_TEST_URL", settings.DATABASE_TEST_URL)
_WORKER = os.getenv("PYTEST_XDIST_WORKER", "master")


def _server_url() -> str:
    return BASE_URL.rsplit("/", 1)[0] + "/postgres"


def _url(database: str) -> str:
    return BASE_URL.rsplit("/", 1)[0] + f"/{database}"


def _alembic_at(database: str, revision: str) -> None:
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
    _alembic_at(database, UNIQUE_USER_ID)

    yield engine

    engine.dispose()
    with admin.connect() as conn:
        conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'))
    admin.dispose()


DUPLICATES = """
    INSERT INTO persons (first_name, last_name, email) VALUES
        ('Rejoined', 'Member', 'rejoined@migration.test'),
        ('TwiceCancelled', 'Member', 'twice-cancelled@migration.test'),
        ('Single', 'Member', 'single@migration.test');

    INSERT INTO users (person_id, email, password_hash) VALUES
        ((SELECT id FROM persons WHERE email = 'rejoined@migration.test'),
         'rejoined@migration.test', 'x'),
        ((SELECT id FROM persons WHERE email = 'twice-cancelled@migration.test'),
         'twice-cancelled@migration.test', 'x'),
        ((SELECT id FROM persons WHERE email = 'single@migration.test'),
         'single@migration.test', 'x');

    -- Cancelled first, active second: the lower id is the one a bare
    -- unordered `.first()` would have been likely to return.
    INSERT INTO members (person_id, user_id, member_number, status, is_active, joined_at)
    VALUES
        ((SELECT id FROM persons WHERE email = 'rejoined@migration.test'),
         (SELECT id FROM users WHERE email = 'rejoined@migration.test'),
         'M-CANCELLED', 'cancelled', false, current_date),
        ((SELECT id FROM persons WHERE email = 'rejoined@migration.test'),
         (SELECT id FROM users WHERE email = 'rejoined@migration.test'),
         'M-ACTIVE', 'active', true, current_date);

    -- Both cancelled: the migration has no "active" row to prefer, so the
    -- most recently created one should win.
    INSERT INTO members (person_id, user_id, member_number, status, is_active, joined_at)
    VALUES
        ((SELECT id FROM persons WHERE email = 'twice-cancelled@migration.test'),
         (SELECT id FROM users WHERE email = 'twice-cancelled@migration.test'),
         'M-OLDER', 'cancelled', false, current_date),
        ((SELECT id FROM persons WHERE email = 'twice-cancelled@migration.test'),
         (SELECT id FROM users WHERE email = 'twice-cancelled@migration.test'),
         'M-NEWER', 'cancelled', false, current_date);

    -- Control: a single, unduplicated member row must be left exactly as it is.
    INSERT INTO members (person_id, user_id, member_number, status, is_active, joined_at)
    VALUES
        ((SELECT id FROM persons WHERE email = 'single@migration.test'),
         (SELECT id FROM users WHERE email = 'single@migration.test'),
         'M-SINGLE', 'active', true, current_date);
"""


@pytest.fixture(scope="module")
def migrated(request):
    yield from _install("members_user_id_unique", DUPLICATES)


def _linked_member_numbers(engine, email: str) -> list[str]:
    with engine.connect() as conn:
        return [
            row[0]
            for row in conn.execute(
                sa.text(
                    "SELECT m.member_number FROM members m "
                    "JOIN users u ON u.id = m.user_id "
                    "WHERE u.email = :email"
                ),
                {"email": email},
            ).all()
        ]


class TestExistingDuplicatesAreResolved:
    def test_the_active_row_keeps_the_link(self, migrated):
        assert _linked_member_numbers(migrated, "rejoined@migration.test") == ["M-ACTIVE"]

    def test_the_detached_row_is_not_deleted(self, migrated):
        with migrated.connect() as conn:
            status = conn.execute(
                sa.text("SELECT status FROM members WHERE member_number = 'M-CANCELLED'")
            ).scalar_one()

        assert status == "cancelled"

    def test_between_two_cancelled_rows_the_most_recent_keeps_the_link(self, migrated):
        assert _linked_member_numbers(migrated, "twice-cancelled@migration.test") == [
            "M-NEWER"
        ]

    def test_an_unduplicated_member_is_untouched(self, migrated):
        assert _linked_member_numbers(migrated, "single@migration.test") == ["M-SINGLE"]


class TestConstraintIsEnforcedGoingForward:
    def test_a_second_row_for_the_same_user_is_rejected(self, migrated):
        with migrated.connect() as conn:
            user_id = conn.execute(
                sa.text("SELECT id FROM users WHERE email = 'single@migration.test'")
            ).scalar_one()
            person_id = conn.execute(
                sa.text("SELECT id FROM persons WHERE email = 'single@migration.test'")
            ).scalar_one()

            with pytest.raises(sa.exc.IntegrityError):
                conn.execute(
                    sa.text(
                        "INSERT INTO members (person_id, user_id, status, is_active, joined_at) "
                        "VALUES (:person_id, :user_id, 'active', true, current_date)"
                    ),
                    {"person_id": person_id, "user_id": user_id},
                )
