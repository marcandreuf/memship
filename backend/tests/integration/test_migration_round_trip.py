"""The whole 2.19.0 to 3.0.0 chain, down and back up, against real data.

Two tests already downgrade a migration: ``test_roles_migration.py`` and
``test_settings_split_migration.py``. Both are scoped to one step. The settings
split round-trips ``26ed04f8781e`` to ``7b3c9e2a4d51`` and back, which is the
*last* of the eight revisions in this chain, so it never reaches
``29a3872dad10`` four steps below it.

That gap is why a data-independent schema error shipped in v3.0.0: the
``members`` backfill in ``29a3872dad10``'s ``downgrade()`` reads a ``users``
column the same function has not recreated yet, so every downgrade from 3.0.0
fails identically regardless of what the database holds (memship#474). A
chain-level round trip catches it in seconds; nothing performed one.

Nothing re-upgrades either, which is how memship#475 survived: the downgrade
drops ``contact_types.channel`` but leaves the rows the upgrade inserted, and
the second upgrade then violates ``contacts_channel_matches_type``.

The seam is the alembic CLI against a throwaway database, as in the two tests
above, observed through SQL. A freshly migrated 2.19.0 database carries **no**
``contact_types`` rows: the six an installation has come from
``app.cli.seed.seed_contact_types``, not from a migration. The fixture seeds
them itself so the baseline it asserts a return to is explicit.
"""

import hashlib
import os

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.core.config import settings

BASE_URL = os.getenv("DATABASE_TEST_URL", settings.DATABASE_TEST_URL)
_WORKER = os.getenv("PYTEST_XDIST_WORKER", "master")
SCRATCH = f"memship_round_trip_test_{_WORKER}"

# v2.19.0's alembic head, and the head of the chain under test (v3.0.0).
BASE = "d6f0e949ffef"
HEAD = "7b3c9e2a4d51"

# What app.cli.seed.seed_contact_types creates. Every code here has a prefix in
# the split_part allow-list of e3f8c2a91b47, so all six survive the channel
# backfill; only the `website` type the migration itself seeds does not.
BASELINE_CONTACT_TYPES = [
    ("phone_home", "Home Phone", 1),
    ("phone_mobile", "Mobile Phone", 2),
    ("phone_work", "Work Phone", 3),
    ("phone_emergency", "Emergency Phone", 4),
    ("email_work", "Work Email", 5),
    ("email_other", "Other Email", 6),
]


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


@pytest.fixture
def scratch_db():
    """Rebuilt per test. The whole chain from zero runs in about two seconds,
    so paying it per test buys full independence: these tests mutate schema,
    and a shared database would make them order-dependent."""
    admin = sa.create_engine(_server_url(), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{SCRATCH}" WITH (FORCE)'))
            conn.execute(sa.text(f'CREATE DATABASE "{SCRATCH}"'))
    except sa.exc.OperationalError as exc:
        pytest.skip(f"no database server for the round-trip test: {exc}")

    engine = sa.create_engine(_scratch_url())
    yield engine

    engine.dispose()
    with admin.connect() as conn:
        conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{SCRATCH}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture
def round_tripped(scratch_db):
    """Seeded at 2.19.0, upgraded to the 3.0.0 head, then downgraded back.

    Yields the engine and the fingerprint taken at the top of the chain, so a
    test can assert what survived the descent.
    """
    _alembic_to(BASE)
    _seed_2_19(scratch_db)
    _alembic_to(HEAD)
    at_head = _fingerprint(scratch_db)

    _alembic_to(BASE, down=True)

    return scratch_db, at_head


def _seed_2_19(engine) -> None:
    """A club with members, logins, receipts and the seeded contact types.

    `organization_settings.phone` and `website` are set deliberately: the club
    contacts that `7b3c9e2a4d51` inserts are guarded by
    `WHERE COALESCE(o.website, '') <> ''`, so without a website the path that
    memship#475 breaks never runs.
    """
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO organization_settings (id, name, legal_name, email, phone, website) "
            "VALUES (1, 'Club Round Trip', 'Club Round Trip SL', 'info@club.test', "
            "        '+34 600 111 222', 'https://club.test')"
        ))
        for code, name, order in BASELINE_CONTACT_TYPES:
            conn.execute(sa.text(
                "INSERT INTO contact_types (code, name, description, display_order, is_active) "
                "VALUES (:c, :n, :n, :o, true)"
            ), {"c": code, "n": name, "o": order})

        # Three members: one with a login, two without. The login is what
        # 29a3872dad10's downgrade has to repopulate into members.user_id.
        for i in range(1, 4):
            person_id = conn.execute(sa.text(
                "INSERT INTO persons (first_name, last_name, email) "
                "VALUES (:f, 'Roundtrip', :e) RETURNING id"
            ), {"f": f"Member{i}", "e": f"member{i}@example.org"}).scalar_one()

            user_id = None
            if i == 1:
                user_id = conn.execute(sa.text(
                    "INSERT INTO users (person_id, email, password_hash, is_active) "
                    "VALUES (:p, :e, 'x', true) RETURNING id"
                ), {"p": person_id, "e": f"member{i}@example.org"}).scalar_one()

            member_id = conn.execute(sa.text(
                "INSERT INTO members (person_id, user_id, member_number, status, is_active) "
                "VALUES (:p, :u, :mn, 'active', true) RETURNING id"
            ), {"p": person_id, "u": user_id, "mn": f"M{i:04d}"}).scalar_one()

            conn.execute(sa.text(
                "INSERT INTO receipts (receipt_number, member_id, origin, description, "
                "  base_amount, vat_rate, vat_amount, total_amount, status, "
                "  emission_date, is_batchable, is_active) "
                "VALUES (:rn, :m, 'membership', 'Annual fee', "
                "  100.00, 21.00, 21.00, 121.00, 'paid', "
                "  '2026-01-15', true, true)"
            ), {"rn": f"R{i:04d}", "m": member_id})


def _fingerprint(engine) -> dict:
    """Counts and digests that must survive a round trip untouched."""
    with engine.connect() as conn:
        numbers = conn.execute(
            sa.text("SELECT member_number FROM members ORDER BY member_number")
        ).scalars().all()
        return {
            "persons": conn.execute(sa.text("SELECT count(*) FROM persons")).scalar_one(),
            "members": conn.execute(sa.text("SELECT count(*) FROM members")).scalar_one(),
            "receipts": conn.execute(sa.text("SELECT count(*) FROM receipts")).scalar_one(),
            "receipt_total": conn.execute(
                sa.text("SELECT coalesce(sum(total_amount), 0) FROM receipts")
            ).scalar_one(),
            "member_numbers": hashlib.md5(
                "|".join(n or "" for n in numbers).encode()
            ).hexdigest(),
        }


def _revision(engine) -> str:
    with engine.connect() as conn:
        return conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()


class TestTheChainGoesDownAgain:
    def test_the_full_chain_downgrades(self, scratch_db):
        """memship#474: every downgrade from 3.0.0 fails on the fifth revision
        it reverts, before any data is consulted."""
        _alembic_to(BASE)
        _seed_2_19(scratch_db)
        _alembic_to(HEAD)
        assert _revision(scratch_db) == HEAD

        _alembic_to(BASE, down=True)

        assert _revision(scratch_db) == BASE

    def test_the_contact_types_it_seeded_are_gone(self, round_tripped):
        """memship#475: the downgrade removes the contacts it created but not
        the two contact_types behind them, so the table is left with rows the
        2.19.0 baseline never had."""
        engine, _ = round_tripped

        with engine.connect() as conn:
            codes = conn.execute(
                sa.text("SELECT code FROM contact_types ORDER BY code")
            ).scalars().all()

        assert codes == sorted(c for c, _, _ in BASELINE_CONTACT_TYPES)

    def test_the_data_comes_back(self, round_tripped):
        """The descent is allowed to cost reversibility, never rows."""
        engine, at_head = round_tripped

        assert _fingerprint(engine) == at_head

    def test_a_login_is_restored_to_its_member(self, round_tripped):
        """members.user_id is dropped on the way up and rebuilt on the way
        down from users.person_id. Reaching the bottom without an error is not
        the same as rebuilding it, so assert the link, not just the exit."""
        engine, _ = round_tripped

        with engine.connect() as conn:
            links = dict(conn.execute(sa.text(
                "SELECT member_number, user_id FROM members ORDER BY member_number"
            )).all())

        assert links["M0001"] is not None, "the member holding a login lost it"
        assert links["M0002"] is None
        assert links["M0003"] is None

    def test_it_upgrades_again(self, round_tripped):
        """A downgrade that cannot be followed by an upgrade is a one-way
        door. This is the half of memship#475 that the leaked rows broke."""
        engine, at_head = round_tripped

        _alembic_to(HEAD)

        assert _revision(engine) == HEAD
        assert _fingerprint(engine) == at_head


class TestTheUpgradeDoesNotAssumeACleanTable:
    """The seed at `7b3c9e2a4d51:96` matched on `code` alone and skipped any row
    it found, inheriting whatever channel that row carried. Combined with the
    `split_part` derivation in `e3f8c2a91b47`, which cannot resolve a code
    without an underscore and falls back to 'other', a pre-existing `website`
    type was enough to break the upgrade on the composite foreign key.

    Nothing in the product can create that state: `contact_types` is seed-only
    data and the API exposes a single GET. That is precisely why this is a
    defensive property rather than a reachable bug, and why it is asserted here
    instead of being left to the next person to rediscover.
    """

    def test_a_pre_existing_website_type_is_repaired_not_inherited(self, scratch_db):
        _alembic_to(BASE)
        _seed_2_19(scratch_db)
        with scratch_db.begin() as conn:
            conn.execute(sa.text(
                "INSERT INTO contact_types (code, name, description, display_order, is_active) "
                "VALUES ('website', 'Website', 'Pre-existing', 7, true)"
            ))

        _alembic_to(HEAD)

        assert _revision(scratch_db) == HEAD
        with scratch_db.connect() as conn:
            channel = conn.execute(sa.text(
                "SELECT channel FROM contact_types WHERE code = 'website'"
            )).scalar_one()
        assert channel == "url"
