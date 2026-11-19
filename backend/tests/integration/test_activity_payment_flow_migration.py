"""The payment-flow migration, run for real against a throwaway database.

The rest of the suite builds its schema with ``create_all``, so nothing else would
notice if an install that upgrades rather than starts fresh stopped stamping its
existing activities ``legacy``. That stamp is the whole promise to a club with
activities already running: none of them changes behaviour.
"""

import pytest
import sqlalchemy as sa

from tests.integration.test_default_tier_migration import (
    _WORKER,
    _alembic_at,
    _server_url,
    _url,
)

BEFORE = "c4e9a71b2d38"
AFTER = "d5a2c8e41f67"

ACTIVITY = """
    INSERT INTO activities (name, slug, starts_at, ends_at, registration_starts_at,
                            registration_ends_at, max_participants)
    VALUES ('{name}', '{slug}', now() + interval '10 days', now() + interval '11 days',
            now() - interval '1 day', now() + interval '9 days', 20)
"""


@pytest.fixture(scope="module")
def upgraded():
    database = f"memship_payment_flow_migration_test_{_WORKER}"
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
        conn.execute(sa.text(ACTIVITY.format(name="Running", slug="running")))
    _alembic_at(database, AFTER)

    yield engine

    engine.dispose()
    with admin.connect() as conn:
        conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'))
    admin.dispose()


class TestAnActivityThatPredatesTheFlow:
    def test_is_stamped_legacy(self, upgraded):
        with upgraded.connect() as conn:
            flow = conn.execute(
                sa.text("SELECT payment_flow FROM activities WHERE slug = 'running'")
            ).scalar_one()
        assert flow == "legacy"

    def test_has_no_methods_and_no_auto_cancel_override(self, upgraded):
        with upgraded.connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT payment_methods, auto_cancel_enabled, auto_cancel_hours "
                    "FROM activities WHERE slug = 'running'"
                )
            ).one()
        assert tuple(row) == ([], None, None)


class TestAnActivityCreatedAfterwards:
    def test_defaults_to_the_new_flow(self, upgraded):
        with upgraded.begin() as conn:
            conn.execute(sa.text(ACTIVITY.format(name="Fresh", slug="fresh")))
            flow = conn.execute(
                sa.text("SELECT payment_flow FROM activities WHERE slug = 'fresh'")
            ).scalar_one()
        assert flow == "pay_to_confirm"

    @pytest.mark.parametrize(
        "assignment",
        ["payment_flow = 'other'", "payment_methods = ARRAY['paypal']::varchar[]"],
    )
    def test_the_database_refuses_values_outside_the_vocabulary(
        self, upgraded, assignment
    ):
        with pytest.raises(sa.exc.IntegrityError):
            with upgraded.begin() as conn:
                conn.execute(
                    sa.text(f"UPDATE activities SET {assignment} WHERE slug = 'running'")
                )
