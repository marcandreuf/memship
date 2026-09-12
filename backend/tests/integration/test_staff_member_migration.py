"""`e2f3a4b5c6d7`, run for real against a throwaway database.

Taking staff out of the member register is a delete, so the interesting cases
are the ones it must *not* touch: a plain member, and a staff account whose
member row is referenced by billing it would be wrong to silently unpick.

The rest of the suite builds its schema with ``create_all`` and never runs
alembic, so nothing else would notice if this regressed on an install that
upgrades rather than starts fresh.
"""

import os
from datetime import date

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.core.config import settings

BEFORE = "9c1d2e3f4a5b"
STAFF_OUT = "e2f3a4b5c6d7"

BASE_URL = os.getenv("DATABASE_TEST_URL", settings.DATABASE_TEST_URL)
_WORKER = os.getenv("PYTEST_XDIST_WORKER", "master")
SCRATCH = f"memship_staff_member_migration_test_{_WORKER}"


def _server_url() -> str:
    return BASE_URL.rsplit("/", 1)[0] + "/postgres"


def _scratch_url() -> str:
    return BASE_URL.rsplit("/", 1)[0] + f"/{SCRATCH}"


def _alembic_at(revision: str) -> None:
    """Migrate the scratch database, not whatever ``DATABASE_URL`` points at.

    ``alembic/env.py`` overrides the configured URL from the environment, so
    without setting it here CI would migrate the shared test database that
    hundreds of other tests are using concurrently.
    """
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


def _account(conn, email: str, slugs: tuple[str, ...], membership_type_id: int) -> int:
    """An account in the shape the old code produced: roles plus a member row."""
    person_id = conn.execute(
        sa.text(
            "INSERT INTO persons (first_name, last_name, email) "
            "VALUES ('Legacy', 'Account', :e) RETURNING id"
        ),
        {"e": email},
    ).scalar_one()
    user_id = conn.execute(
        sa.text(
            "INSERT INTO users (person_id, email, password_hash, is_active) "
            "VALUES (:p, :e, 'x', true) RETURNING id"
        ),
        {"p": person_id, "e": email},
    ).scalar_one()
    for slug in slugs:
        conn.execute(
            sa.text(
                "INSERT INTO user_roles (user_id, role_id) "
                "SELECT :u, id FROM roles WHERE slug = :s"
            ),
            {"u": user_id, "s": slug},
        )
    member_id = conn.execute(
        sa.text(
            "INSERT INTO members (person_id, user_id, membership_type_id, "
            "member_number, status, joined_at) "
            "VALUES (:p, :u, :mt, :n, 'active', :d) RETURNING id"
        ),
        {
            "p": person_id,
            "u": user_id,
            "mt": membership_type_id,
            "n": f"M-{user_id:04d}",
            "d": date(2026, 1, 1),
        },
    ).scalar_one()
    return member_id


@pytest.fixture(scope="module")
def migrated(scratch_db):
    """Build the pre-#168 world at the revision before the fix, then upgrade."""
    _alembic_at(BEFORE)

    with scratch_db.begin() as conn:
        membership_type_id = conn.execute(
            sa.text(
                "INSERT INTO membership_types (name, slug, base_price, billing_frequency) "
                "VALUES ('Legacy Full', 'legacy-full', 50, 'annual') RETURNING id"
            )
        ).scalar_one()

        _account(conn, "super@migration.test", ("super_admin", "member"), membership_type_id)
        _account(conn, "admin@migration.test", ("admin", "member"), membership_type_id)
        _account(conn, "member@migration.test", ("member",), membership_type_id)

        billed = _account(
            conn, "billed-admin@migration.test", ("admin", "member"), membership_type_id
        )
        conn.execute(
            sa.text(
                "INSERT INTO receipts (receipt_number, member_id, origin, description, "
                "base_amount, vat_rate, vat_amount, total_amount, status, emission_date, "
                "is_batchable, is_active) "
                "VALUES ('R-0001', :m, 'membership', 'Legacy fee', 100, 0, 0, 100, "
                "'paid', :d, false, true)"
            ),
            {"m": billed, "d": date(2026, 1, 15)},
        )

    _alembic_at(STAFF_OUT)
    return scratch_db


def _roles(engine, email: str) -> set[str]:
    with engine.connect() as conn:
        return {
            slug
            for (slug,) in conn.execute(
                sa.text(
                    "SELECT r.slug FROM users u "
                    "JOIN user_roles ur ON ur.user_id = u.id "
                    "JOIN roles r ON r.id = ur.role_id "
                    "WHERE u.email = :e"
                ),
                {"e": email},
            ).all()
        }


def _has_member_row(engine, email: str) -> bool:
    with engine.connect() as conn:
        return conn.execute(
            sa.text(
                "SELECT count(*) FROM members m JOIN users u ON u.id = m.user_id "
                "WHERE u.email = :e"
            ),
            {"e": email},
        ).scalar_one() > 0


class TestStaffLeaveTheRegister:
    @pytest.mark.parametrize(
        "email,role",
        [("super@migration.test", "super_admin"), ("admin@migration.test", "admin")],
    )
    def test_the_member_record_and_role_both_go(self, migrated, email, role):
        assert _has_member_row(migrated, email) is False
        assert _roles(migrated, email) == {role}

    def test_the_staff_role_survives_so_nothing_holds_no_roles(self, migrated):
        for email in ("super@migration.test", "admin@migration.test"):
            assert _roles(migrated, email) != set()


class TestWhatItMustNotTouch:
    def test_a_plain_member_keeps_everything(self, migrated):
        assert _has_member_row(migrated, "member@migration.test") is True
        assert _roles(migrated, "member@migration.test") == {"member"}

    def test_a_staff_account_with_billing_is_left_for_a_person_to_sort_out(
        self, migrated
    ):
        """The receipt would make the delete fail outright, and an account with
        billing history behind it is a decision, not a migration's business.
        Role and row stay together rather than half-applying."""
        assert _has_member_row(migrated, "billed-admin@migration.test") is True
        assert _roles(migrated, "billed-admin@migration.test") == {"admin", "member"}

    def test_the_receipt_still_points_at_its_member(self, migrated):
        with migrated.connect() as conn:
            orphans = conn.execute(
                sa.text(
                    "SELECT count(*) FROM receipts r "
                    "LEFT JOIN members m ON m.id = r.member_id WHERE m.id IS NULL"
                )
            ).scalar_one()

        assert orphans == 0
