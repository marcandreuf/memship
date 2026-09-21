"""The whitespace-trimming email migration, run for real against a throwaway
database (#265).

Mirrors ``test_member_user_id_migration.py``: the rest of the suite builds its
schema with ``create_all`` and never invokes alembic, so nothing else would
notice a padded legacy row surviving the upgrade.
"""

import os

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.core.config import settings

BEFORE = "20f5b7a3c3f3"
TRIM = "7c1e2d3f4a5b"

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


def _fresh_database(name: str):
    database = f"memship_{name}_migration_test_{_WORKER}"
    admin = sa.create_engine(_server_url(), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'))
            conn.execute(sa.text(f'CREATE DATABASE "{database}"'))
    except sa.exc.OperationalError as exc:
        admin.dispose()
        pytest.skip(f"no database server for the migration test: {exc}")
    return database, admin


def _drop(database: str, admin) -> None:
    with admin.connect() as conn:
        conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'))
    admin.dispose()


# Written the way a script would have before v2.12.0: raw SQL, no ORM
# validator, tabs and newlines around the address. `f5a6b7c8d9e0` lower-cased
# these and left the padding.
PADDED = """
    INSERT INTO persons (first_name, last_name, email) VALUES
        ('Tabbed', 'Member', E'\\ttabbed@migration.test'),
        ('Newlined', 'Member', E'newlined@migration.test\\n'),
        ('Clean', 'Member', 'clean@migration.test');

    INSERT INTO users (person_id, email, password_hash) VALUES
        ((SELECT id FROM persons WHERE email = E'\\ttabbed@migration.test'),
         E'\\ttabbed@migration.test', 'x'),
        ((SELECT id FROM persons WHERE email = E'newlined@migration.test\\n'),
         E'newlined@migration.test\\n', 'x'),
        ((SELECT id FROM persons WHERE email = 'clean@migration.test'),
         'clean@migration.test', 'x');
"""

# A padded row and a clean row that become the same address once trimmed:
# two logins, so the migration must refuse rather than merge them.
COLLIDING = """
    INSERT INTO persons (first_name, last_name, email) VALUES
        ('Padded', 'Twin', E'\\ttwin@migration.test'),
        ('Clean', 'Twin', 'twin@migration.test');

    INSERT INTO users (person_id, email, password_hash) VALUES
        ((SELECT id FROM persons WHERE email = E'\\ttwin@migration.test'),
         E'\\ttwin@migration.test', 'x'),
        ((SELECT id FROM persons WHERE email = 'twin@migration.test'),
         'twin@migration.test', 'x');
"""


def _emails(engine, table: str) -> list[str]:
    with engine.connect() as conn:
        return sorted(
            row[0]
            for row in conn.execute(sa.text(f"SELECT email FROM {table}")).all()
        )


@pytest.fixture(scope="module")
def migrated():
    database, admin = _fresh_database("email_whitespace")
    _alembic_at(database, BEFORE)
    engine = sa.create_engine(_url(database))
    with engine.begin() as conn:
        conn.execute(sa.text(PADDED))
    _alembic_at(database, TRIM)
    yield engine
    engine.dispose()
    _drop(database, admin)


class TestPaddedRowsAreTrimmed:
    def test_users(self, migrated):
        assert _emails(migrated, "users") == [
            "clean@migration.test",
            "newlined@migration.test",
            "tabbed@migration.test",
        ]

    def test_persons(self, migrated):
        assert _emails(migrated, "persons") == [
            "clean@migration.test",
            "newlined@migration.test",
            "tabbed@migration.test",
        ]


class TestACollisionRefuses:
    def test_it_refuses_and_writes_nothing(self):
        database, admin = _fresh_database("email_whitespace_collision")
        try:
            _alembic_at(database, BEFORE)
            engine = sa.create_engine(_url(database))
            with engine.begin() as conn:
                conn.execute(sa.text(COLLIDING))

            with pytest.raises(RuntimeError, match="twin@migration.test"):
                _alembic_at(database, TRIM)

            # Untouched: the padded row still has its tab.
            assert _emails(engine, "users") == [
                "\ttwin@migration.test",
                "twin@migration.test",
            ]
            engine.dispose()
        finally:
            _drop(database, admin)
