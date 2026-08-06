"""The roles migration, run for real against a throwaway database.

The rest of the suite builds its schema with ``create_all`` and never exercises
alembic, so nothing else would notice if the backfill regressed on an install
that upgrades rather than starts fresh.
"""

import os

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.core.config import settings

BEFORE = "c5d6e7f8a9b0"
ROLES = "d1a2b3c4e5f6"

BASE_URL = os.getenv("DATABASE_TEST_URL", settings.DATABASE_TEST_URL)
# Suffixed per xdist worker (gw0, gw1, ...) so parallel workers don't race
# DROP/CREATE DATABASE against the same scratch database.
_WORKER = os.getenv("PYTEST_XDIST_WORKER", "master")
SCRATCH = f"memship_roles_migration_test_{_WORKER}"


def _server_url() -> str:
    return BASE_URL.rsplit("/", 1)[0] + "/postgres"


def _scratch_url() -> str:
    return BASE_URL.rsplit("/", 1)[0] + f"/{SCRATCH}"


def _alembic_at(revision: str) -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", _scratch_url())
    command.upgrade(cfg, revision)


@pytest.fixture(scope="module")
def scratch_db():
    admin = sa.create_engine(_server_url(), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{SCRATCH}" WITH (FORCE)'))
            conn.execute(sa.text(f'CREATE DATABASE "{SCRATCH}"'))
    except sa.exc.OperationalError as exc:
        pytest.skip(f"no database server for the migration test: {exc}")

    engine = sa.create_engine(_scratch_url())
    yield engine

    engine.dispose()
    with admin.connect() as conn:
        conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{SCRATCH}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture(scope="module")
def migrated(scratch_db):
    """Seed one user per legacy role at the revision before roles, then upgrade."""
    _alembic_at(BEFORE)

    with scratch_db.begin() as conn:
        for role in ("super_admin", "admin", "member", "restricted"):
            person_id = conn.execute(
                sa.text(
                    "INSERT INTO persons (first_name, last_name, email) "
                    "VALUES (:f, 'Legacy', :e) RETURNING id"
                ),
                {"f": role, "e": f"{role}@migration.test"},
            ).scalar_one()
            conn.execute(
                sa.text(
                    "INSERT INTO users (person_id, email, password_hash, role, is_active) "
                    "VALUES (:p, :e, 'x', :r, true)"
                ),
                {"p": person_id, "e": f"{role}@migration.test", "r": role},
            )

    _alembic_at(ROLES)
    return scratch_db


def _assignments(engine) -> dict[str, set[str]]:
    with engine.connect() as conn:
        rows = conn.execute(
            sa.text(
                "SELECT u.email, r.slug FROM users u "
                "JOIN user_roles ur ON ur.user_id = u.id "
                "JOIN roles r ON r.id = ur.role_id"
            )
        ).all()
    out: dict[str, set[str]] = {}
    for email, slug in rows:
        out.setdefault(email, set()).add(slug)
    return out


class TestBackfill:
    def test_admin_keeps_admin_and_gains_member(self, migrated):
        assert _assignments(migrated)["admin@migration.test"] == {"admin", "member"}

    def test_super_admin_keeps_super_admin_and_gains_member(self, migrated):
        assert _assignments(migrated)["super_admin@migration.test"] == {
            "super_admin",
            "member",
        }

    def test_member_gets_member(self, migrated):
        assert _assignments(migrated)["member@migration.test"] == {"member"}

    def test_restricted_downgrades_to_member_only(self, migrated):
        """A strict downgrade. Mapping it to a staff role would have *granted*
        access the tier never had."""
        assert _assignments(migrated)["restricted@migration.test"] == {"member"}

    def test_no_user_is_left_without_a_role(self, migrated):
        with migrated.connect() as conn:
            orphans = conn.execute(
                sa.text(
                    "SELECT count(*) FROM users u WHERE NOT EXISTS "
                    "(SELECT 1 FROM user_roles r WHERE r.user_id = u.id)"
                )
            ).scalar_one()

        assert orphans == 0


class TestSeededRoles:
    def test_super_admin_stores_no_permission_rows(self, migrated):
        from app.core.permissions import ADMIN_SEED_KEYS, MEMBER_SEED_KEYS

        with migrated.connect() as conn:
            counts = dict(
                conn.execute(
                    sa.text(
                        "SELECT r.slug, count(rp.permission_key) FROM roles r "
                        "LEFT JOIN role_permissions rp ON rp.role_id = r.id "
                        "GROUP BY r.slug"
                    )
                ).all()
            )

        assert counts["super_admin"] == 0
        assert counts["admin"] == len(ADMIN_SEED_KEYS)
        assert counts["member"] == len(MEMBER_SEED_KEYS)

    def test_admin_is_seeded_without_the_super_admin_only_keys(self, migrated):
        with migrated.connect() as conn:
            keys = {
                k
                for (k,) in conn.execute(
                    sa.text(
                        "SELECT rp.permission_key FROM role_permissions rp "
                        "JOIN roles r ON r.id = rp.role_id WHERE r.slug = 'admin'"
                    )
                ).all()
            }

        assert "roles.write" not in keys
        assert "settings.integrations.write" not in keys
        assert "settings.custom_fields.write" not in keys


class TestColumnsDropped:
    def test_users_role_and_permissions_are_gone(self, migrated):
        with migrated.connect() as conn:
            columns = {
                c
                for (c,) in conn.execute(
                    sa.text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'users'"
                    )
                ).all()
            }

        assert "role" not in columns
        assert "permissions" not in columns


class TestDowngrade:
    def test_downgrade_restores_a_single_role_per_user(self, migrated):
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", _scratch_url())
        command.downgrade(cfg, BEFORE)

        with migrated.connect() as conn:
            roles = dict(conn.execute(sa.text("SELECT email, role FROM users")).all())

        assert roles["admin@migration.test"] == "admin"
        assert roles["super_admin@migration.test"] == "super_admin"
        assert roles["member@migration.test"] == "member"
        # Lossy by design: the tier is unrecoverable once backfilled.
        assert roles["restricted@migration.test"] == "member"