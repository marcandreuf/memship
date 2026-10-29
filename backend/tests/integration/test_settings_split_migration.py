"""The Phase 5c settings split migration, run for real against a throwaway DB.

The rest of the suite builds its schema with ``create_all``; only this module
proves the data moves: settings values overwrite the party's stale Phase 3
copies, phone/website become club contact rows, both bank columns trios land
in ``bank_accounts``, and the downgrade restores every column from the rows
the upgrade created.
"""

import os

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.core.config import settings

BEFORE = "26ed04f8781e"
SPLIT = "7b3c9e2a4d51"

BASE_URL = os.getenv("DATABASE_TEST_URL", settings.DATABASE_TEST_URL)
_WORKER = os.getenv("PYTEST_XDIST_WORKER", "master")
SCRATCH = f"memship_settings_split_test_{_WORKER}"


def _server_url() -> str:
    return BASE_URL.rsplit("/", 1)[0] + "/postgres"


def _scratch_url() -> str:
    return BASE_URL.rsplit("/", 1)[0] + f"/{SCRATCH}"


def _alembic_to(revision: str, *, down: bool = False) -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", _scratch_url())
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = _scratch_url()
    try:
        (command.downgrade if down else command.upgrade)(cfg, revision)
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


@pytest.fixture(scope="module")
def migrated(scratch_db):
    """Seed a club with drifted party copies and a banked member at the
    revision before the split, then upgrade through it."""
    _alembic_to(BEFORE)

    with scratch_db.begin() as conn:
        club_party = conn.execute(sa.text(
            "INSERT INTO party (kind, display_name, national_id, email, photo_url) "
            "VALUES ('association', 'Stale Old Name', 'STALE', 'stale@club.test', NULL) "
            "RETURNING id"
        )).scalar_one()
        conn.execute(sa.text(
            "INSERT INTO organization_settings "
            "(id, party_id, name, legal_name, email, phone, website, logo_url, tax_id, "
            " locale, timezone, currency, date_format, "
            " bank_name, bank_iban, bank_bic, creditor_id) "
            "VALUES (1, :p, 'Club Nou', 'Club Nou SL', 'info@club.test', '+34 600 111 222', "
            " 'https://club.test', '/logo.png', 'G99999999', "
            " 'es', 'Europe/Madrid', 'EUR', 'DD/MM/YYYY', "
            " 'CaixaBank', 'ES9121000418450200051332', 'CAIXESBBXXX', 'ES12000B12345678')"
        ), {"p": club_party})

        person_party = conn.execute(sa.text(
            "INSERT INTO party (kind, display_name) "
            "VALUES ('person', 'Banked Member') RETURNING id"
        )).scalar_one()
        conn.execute(sa.text(
            "INSERT INTO persons (party_id, first_name, last_name, "
            " bank_iban, bank_bic, bank_holder_name) "
            "VALUES (:p, 'Banked', 'Member', "
            " 'ES7921000813610123456789', 'CAIXESBBXXX', 'Banked Member')"
        ), {"p": person_party})

        # A person with no bank data must not get an empty account row.
        bare_party = conn.execute(sa.text(
            "INSERT INTO party (kind, display_name) "
            "VALUES ('person', 'Bare Member') RETURNING id"
        )).scalar_one()
        conn.execute(sa.text(
            "INSERT INTO persons (party_id, first_name, last_name) "
            "VALUES (:p, 'Bare', 'Member')"
        ), {"p": bare_party})

    _alembic_to(SPLIT)
    return scratch_db


class TestUpgradeMoves:
    def test_settings_values_overwrite_the_stale_party_copies(self, migrated):
        with migrated.connect() as conn:
            row = conn.execute(sa.text(
                "SELECT p.display_name, p.legal_name, p.national_id, p.email, p.photo_url "
                "FROM party p JOIN organization_settings o ON o.party_id = p.id"
            )).one()
        assert tuple(row) == (
            "Club Nou", "Club Nou SL", "G99999999", "info@club.test", "/logo.png"
        )

    def test_phone_and_website_are_primary_club_contacts(self, migrated):
        with migrated.connect() as conn:
            rows = dict(conn.execute(sa.text(
                "SELECT c.channel, c.value FROM contacts c "
                "JOIN organization_settings o ON o.party_id = c.party_id "
                "WHERE c.is_primary"
            )).all())
        assert rows == {"phone": "+34 600 111 222", "url": "https://club.test"}

    def test_both_bank_trios_land_in_bank_accounts(self, migrated):
        with migrated.connect() as conn:
            club = conn.execute(sa.text(
                "SELECT b.bank_name, b.iban, b.bic FROM bank_accounts b "
                "JOIN organization_settings o ON o.party_id = b.party_id "
                "WHERE b.is_primary"
            )).one()
            member = conn.execute(sa.text(
                "SELECT b.iban, b.bic, b.holder_name FROM bank_accounts b "
                "JOIN persons p ON p.party_id = b.party_id WHERE b.is_primary"
            )).one()
            total = conn.execute(sa.text("SELECT count(*) FROM bank_accounts")).scalar_one()
        assert tuple(club) == ("CaixaBank", "ES9121000418450200051332", "CAIXESBBXXX")
        assert tuple(member) == ("ES7921000813610123456789", "CAIXESBBXXX", "Banked Member")
        assert total == 2  # the bare member got no empty row

    def test_the_columns_are_gone(self, migrated):
        with migrated.connect() as conn:
            org_cols = {c for (c,) in conn.execute(sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'organization_settings'"
            ))}
            person_cols = {c for (c,) in conn.execute(sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'persons'"
            ))}
        assert not org_cols & {"name", "legal_name", "email", "phone", "website",
                               "logo_url", "tax_id", "bank_name", "bank_iban", "bank_bic"}
        assert {"creditor_id", "brand_color"} <= org_cols  # configuration stays
        assert not person_cols & {"bank_iban", "bank_bic", "bank_holder_name"}
        assert "payment_method" in person_cols  # the preference stays


class TestDowngradeRestores:
    """Runs last in the module: it reverts the shared fixture's database."""

    def test_every_value_comes_back(self, migrated):
        _alembic_to(BEFORE, down=True)

        with migrated.connect() as conn:
            org = conn.execute(sa.text(
                "SELECT name, legal_name, email, phone, website, logo_url, tax_id, "
                " bank_name, bank_iban, bank_bic FROM organization_settings"
            )).one()
            person = conn.execute(sa.text(
                "SELECT bank_iban, bank_bic, bank_holder_name FROM persons "
                "WHERE first_name = 'Banked'"
            )).one()
            leftovers = conn.execute(sa.text(
                "SELECT count(*) FROM contacts c "
                "JOIN organization_settings o ON o.party_id = c.party_id"
            )).scalar_one()
            tables = {t for (t,) in conn.execute(sa.text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            ))}

        assert tuple(org) == (
            "Club Nou", "Club Nou SL", "info@club.test", "+34 600 111 222",
            "https://club.test", "/logo.png", "G99999999",
            "CaixaBank", "ES9121000418450200051332", "CAIXESBBXXX",
        )
        assert tuple(person) == ("ES7921000813610123456789", "CAIXESBBXXX", "Banked Member")
        assert leftovers == 0  # the club contact rows the upgrade created are gone
        assert "bank_accounts" not in tables
