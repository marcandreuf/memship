"""The tax-rate migration, run for real against a throwaway database (#605).

Before it, an activity's ``tax_rate = 0`` meant "bill the club's rate". After it,
0 means exempt and NULL inherits. Every 0 already stored was written with the old
meaning, so the migration has to turn it into NULL or every existing activity
would silently start billing 0 %.
"""

from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.domains.billing.service import activity_vat_rate
from tests.integration.test_default_tier_migration import (
    _WORKER,
    _alembic_at,
    _server_url,
    _url,
)

BEFORE = "b7e4c2a9d013"
AFTER = "c4f8a1d27e90"

ACTIVITY = """
    INSERT INTO activities (name, slug, starts_at, ends_at, registration_starts_at,
                            registration_ends_at, max_participants, tax_rate)
    VALUES ('{slug}', '{slug}', now() + interval '10 days', now() + interval '11 days',
            now() - interval '1 day', now() + interval '9 days', 20, {rate})
"""


@pytest.fixture(scope="module")
def upgraded():
    database = f"memship_tax_rate_migration_test_{_WORKER}"
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
        conn.execute(sa.text(ACTIVITY.format(slug="inherits", rate="0")))
        conn.execute(sa.text(ACTIVITY.format(slug="unset", rate="NULL")))
        conn.execute(sa.text(ACTIVITY.format(slug="reduced", rate="10")))
    _alembic_at(database, AFTER)

    yield engine

    engine.dispose()
    with admin.connect() as conn:
        conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'))
    admin.dispose()


def _rate(engine, slug):
    with engine.connect() as conn:
        return conn.execute(
            sa.text("SELECT tax_rate FROM activities WHERE slug = :slug"), {"slug": slug}
        ).scalar_one()


class TestExistingActivities:
    def test_a_zero_becomes_null(self, upgraded):
        assert _rate(upgraded, "inherits") is None

    def test_an_explicit_rate_is_untouched(self, upgraded):
        assert _rate(upgraded, "reduced") == Decimal("10.00")

    @pytest.mark.parametrize(
        "slug, billed", [("inherits", "21"), ("unset", "21"), ("reduced", "10.00")]
    )
    def test_each_keeps_billing_the_rate_it_billed_before(self, upgraded, slug, billed):
        with Session(upgraded) as db:
            assert activity_vat_rate(db, _rate(upgraded, slug)) == Decimal(billed)
