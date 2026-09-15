"""The install path run the way an operator runs it — the CLI as a subprocess.

Every other test of `app.cli.seed` imports its functions and calls them against
a session the test controls. That leaves the module's own entry point — argument
parsing, `main()`, its `SessionLocal`, its commit — unexercised, and it is the
entry point that installs every instance:

    MEMSHIP_ADMIN_PASSWORD='...' python -m app.cli.seed --admin-email you@example.org

The gap this closes is not depth in either suite. It is that nothing both
*seeds an account* and then *authenticates as it* (#196). #191 went out through
that gap twice: the CLI wrote addresses without a schema, so between #193 and
#195 the command above produced a super admin no spelling could sign in as,
with CI fully green — backend tests covered the schemas and the seed helpers in
isolation, the e2e suite only ever signs in as accounts already seeded in lower
case, and `verify-deployment.sh` sees a successful migration and a healthy API.
Nothing failed until a human typed their address.

So these tests deliberately cross the seam rather than test either side of it,
and they use a mixed-case address because that is the input that broke.

The database is a throwaway, built with alembic rather than `create_all`: an
install applies migrations, and the schema the CLI writes into should be the one
a real install has. The subprocess commits, so it cannot share the transactional
`db` fixture.
"""

import os
import subprocess
import sys
from contextlib import contextmanager

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.permissions import SUPER_ADMIN_SLUG

BASE_URL = os.getenv("DATABASE_TEST_URL", settings.DATABASE_TEST_URL)
_WORKER = os.getenv("PYTEST_XDIST_WORKER", "master")
SCRATCH = f"memship_cli_install_path_test_{_WORKER}"

PASSWORD = "correct horse battery staple"

# Deliberately mixed case: this is the input that broke, and the address every
# assertion below expects to find is the normalised form of it.
INSTALL_ADDRESS = "Op.Erator@Example.ORG"
STORED = "op.erator@example.org"


def _server_url() -> str:
    return BASE_URL.rsplit("/", 1)[0] + "/postgres"


def _scratch_url() -> str:
    return BASE_URL.rsplit("/", 1)[0] + f"/{SCRATCH}"


@pytest.fixture(scope="module")
def scratch_db():
    """A database of its own, migrated to head.

    Module-scoped: `alembic upgrade head` is the expensive part and the CLI's
    base-data seeding is idempotent, so the tests share one. Each uses its own
    address, since the subprocess commits and nothing rolls it back.
    """
    admin = sa.create_engine(_server_url(), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{SCRATCH}" WITH (FORCE)'))
            conn.execute(sa.text(f'CREATE DATABASE "{SCRATCH}"'))
    except sa.exc.OperationalError as exc:
        pytest.skip(f"no database server for the install-path test: {exc}")

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", _scratch_url())
    previous = os.environ.get("DATABASE_URL")
    # `alembic/env.py` overrides the configured URL from the environment, so
    # without this the shared test database gets migrated instead.
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


def _seed(*args, password=PASSWORD):
    """Run the module the way the documentation says to run it.

    A real subprocess, so `main()`, the argument parsing and the CLI's own
    session and commit are all in the path. `DATABASE_URL` is what points it at
    the scratch database — `app.db.session` binds its engine to that setting at
    import, the same as it does in the API container.
    """
    env = {**os.environ, "DATABASE_URL": _scratch_url()}
    if password is None:
        env.pop("MEMSHIP_ADMIN_PASSWORD", None)
    else:
        env["MEMSHIP_ADMIN_PASSWORD"] = password
    return subprocess.run(
        [sys.executable, "-m", "app.cli.seed", *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )


@pytest.fixture(scope="module")
def installed(scratch_db):
    """One successful install, shared by the assertions about its outcome.

    The subprocess is the expensive part — a Python interpreter and the whole
    app import, around 2.5s, against 0.7s for every migration in the project —
    so the tests that only need "it installed" share a single run. Each of the
    others drives its own, since what they assert is the run itself.
    """
    result = _seed("--admin-email", INSTALL_ADDRESS)
    assert result.returncode == 0, result.stderr
    return result


@contextmanager
def _api(engine):
    """The real app, talking to the scratch database.

    Not the suite's `client` fixture: that binds to a transaction which is
    rolled back, and the rows under test were committed by another process.
    """
    from fastapi.testclient import TestClient

    from app.db.session import get_db
    from app.main import app

    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


class TestTheDocumentedInstallCommand:
    def test_the_account_it_creates_can_sign_in(self, installed, scratch_db):
        """The assertion that was missing.

        Seeded with capitals, signed in with what a browser sends — the two
        halves that no single test put together before.

        Carried through to an authenticated request rather than stopping at the
        200: login issues a session cookie, and what matters is that the session
        resolves back to this account. A 200 with a cookie nothing accepts would
        still be a locked-out operator.
        """
        with _api(scratch_db) as client:
            response = client.post(
                "/api/v1/auth/login",
                json={"email": STORED, "password": PASSWORD},
            )
            assert response.status_code == 200, response.text
            assert "access_token" in response.cookies

            me = client.get("/api/v1/auth/me")

        assert me.status_code == 200, me.text
        body = me.json()
        assert body["email"] == STORED
        assert SUPER_ADMIN_SLUG in {role["slug"] for role in body["roles"]}
        # Staff are not members (#168), as the portal reads it rather than as
        # the table holds it.
        assert body["member_id"] is None

    def test_it_reports_the_address_as_stored(self, installed):
        """What the operator reads off the terminal has to be what they type."""
        assert STORED in installed.stdout
        assert INSTALL_ADDRESS not in installed.stdout

    def test_the_super_admin_it_creates_is_not_in_the_member_register(
        self, installed, scratch_db
    ):
        """#168's invariant, through the command rather than through a helper.

        Staff are not members. The existing coverage calls `create_staff_user`
        directly, so a regression in what the CLI passes it would not show.
        """
        with scratch_db.connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT u.id, p.id AS person_id FROM users u "
                    "JOIN persons p ON p.id = u.person_id WHERE u.email = :e"
                ),
                {"e": STORED},
            ).one()
            slugs = {
                s
                for (s,) in conn.execute(
                    sa.text(
                        "SELECT r.slug FROM roles r JOIN user_roles ur ON ur.role_id = r.id "
                        "WHERE ur.user_id = :u"
                    ),
                    {"u": row.id},
                )
            }
            members = conn.execute(
                sa.text("SELECT count(*) FROM members WHERE person_id = :p"),
                {"p": row.person_id},
            ).scalar_one()

        assert slugs == {SUPER_ADMIN_SLUG}
        assert members == 0

    def test_rerunning_it_resets_the_password_rather_than_adding_an_account(
        self, scratch_db
    ):
        """The only recovery a super admin has, since password reset refuses them.

        A lookup that missed the existing row would fall through to creating a
        second super admin, which the unique index on `lower(btrim(email))` then
        rejects — turning the recovery path into a crash.
        """
        assert _seed("--admin-email", "Recover@Example.ORG").returncode == 0

        again = _seed("--admin-email", "RECOVER@example.org", password="a whole new password")
        assert again.returncode == 0, again.stderr

        with scratch_db.connect() as conn:
            count = conn.execute(
                sa.text("SELECT count(*) FROM users WHERE email = :e"),
                {"e": "recover@example.org"},
            ).scalar_one()
        assert count == 1

        with _api(scratch_db) as client:
            stale = client.post(
                "/api/v1/auth/login",
                json={"email": "recover@example.org", "password": PASSWORD},
            )
            fresh = client.post(
                "/api/v1/auth/login",
                json={"email": "recover@example.org", "password": "a whole new password"},
            )

        assert stale.status_code == 401
        assert fresh.status_code == 200, fresh.text


class TestItFailsLoudly:
    """`main()` and the argument parsing, which nothing else reaches."""

    def test_it_refuses_without_the_password_variable(self, scratch_db):
        """The password is never an argument — it would land in the shell history."""
        result = _seed("--admin-email", "No.Password@Example.ORG", password=None)

        assert result.returncode != 0
        assert "MEMSHIP_ADMIN_PASSWORD" in result.stderr

        with scratch_db.connect() as conn:
            count = conn.execute(
                sa.text("SELECT count(*) FROM users WHERE email = :e"),
                {"e": "no.password@example.org"},
            ).scalar_one()
        assert count == 0

    def test_it_refuses_a_password_that_is_too_short(self, scratch_db):
        result = _seed("--admin-email", "Short.Pw@Example.ORG", password="short")

        assert result.returncode != 0
        assert "at least 8 characters" in result.stderr

    def test_it_refuses_an_address_belonging_to_a_non_super_admin(self, scratch_db):
        """Resetting a member while reporting a super admin reset hands out
        somebody else's credentials. Asserted through the real exit code."""
        with scratch_db.begin() as conn:
            person_id = conn.execute(
                sa.text(
                    "INSERT INTO persons (first_name, last_name, email) "
                    "VALUES ('Plain', 'Member', 'plain.member@example.org') RETURNING id"
                )
            ).scalar_one()
            conn.execute(
                sa.text(
                    "INSERT INTO users (person_id, email, password_hash, is_active) "
                    "VALUES (:p, 'plain.member@example.org', 'untouched', true)"
                ),
                {"p": person_id},
            )

        result = _seed("--admin-email", "Plain.Member@Example.ORG", password="a whole new password")

        assert result.returncode != 0
        assert "not a" in result.stderr and "super admin" in result.stderr

        with scratch_db.connect() as conn:
            stored = conn.execute(
                sa.text("SELECT password_hash FROM users WHERE email = :e"),
                {"e": "plain.member@example.org"},
            ).scalar_one()
        assert stored == "untouched"
