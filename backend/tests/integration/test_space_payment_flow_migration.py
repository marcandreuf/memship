"""The space payment-flow migration (#603), run for real against a throwaway database.

The rest of the suite builds its schema with ``create_all``, so nothing else would
notice if an upgrade stopped stamping existing spaces ``legacy``, or left ``pending``
out of the index that stops a member holding two rows for one slot.
"""

import pytest
import sqlalchemy as sa

from tests.integration.test_default_tier_migration import (
    _WORKER,
    _alembic_at,
    _server_url,
    _url,
)

BEFORE = "c4f8a1d27e90"
AFTER = "9e4b7c2d1a63"

SPACE = """
    INSERT INTO spaces (name, open_time, close_time)
    VALUES ('{name}', '08:00', '22:00') RETURNING id
"""


@pytest.fixture(scope="module")
def upgraded():
    database = f"memship_space_payment_flow_migration_test_{_WORKER}"
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
        space_id = conn.execute(sa.text(SPACE.format(name="Court"))).scalar_one()
        slot_id = conn.execute(
            sa.text(
                "INSERT INTO space_slots (space_id, slot_date, start_time, end_time) "
                "VALUES (:s, current_date + 3, '10:00', '11:00') RETURNING id"
            ),
            {"s": space_id},
        ).scalar_one()
        party_id = conn.execute(
            sa.text(
                "INSERT INTO party (kind, display_name, email) "
                "VALUES ('person', 'Ana', 'ana@example.org') RETURNING id"
            )
        ).scalar_one()
        conn.execute(
            sa.text(
                "INSERT INTO bookings (space_slot_id, party_id, status) "
                "VALUES (:slot, :party, 'booked')"
            ),
            {"slot": slot_id, "party": party_id},
        )
    _alembic_at(database, AFTER)

    yield engine, slot_id, party_id

    engine.dispose()
    with admin.connect() as conn:
        conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'))
    admin.dispose()


class TestASpaceThatPredatesTheFlow:
    def test_is_stamped_legacy_with_no_methods_or_override(self, upgraded):
        engine, _, _ = upgraded
        with engine.connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT payment_flow, payment_methods, auto_cancel_enabled, "
                    "auto_cancel_hours FROM spaces WHERE name = 'Court'"
                )
            ).one()
        assert tuple(row) == ("legacy", [], None, None)

    def test_its_booking_owes_nothing_and_has_no_deadline(self, upgraded):
        engine, slot_id, _ = upgraded
        with engine.connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT status, refund_status, payment_due_at, pending_since "
                    "FROM bookings WHERE space_slot_id = :s"
                ),
                {"s": slot_id},
            ).one()
        assert tuple(row) == ("booked", "none", None, None)


class TestASpaceCreatedAfterwards:
    def test_defaults_to_the_new_flow(self, upgraded):
        engine, _, _ = upgraded
        with engine.begin() as conn:
            conn.execute(sa.text(SPACE.format(name="Fresh")))
            flow = conn.execute(
                sa.text("SELECT payment_flow FROM spaces WHERE name = 'Fresh'")
            ).scalar_one()
        assert flow == "pay_to_confirm"


class TestTheBookingStatus:
    def test_pending_is_a_status(self, upgraded):
        engine, slot_id, _ = upgraded
        with engine.begin() as conn:
            party_id = conn.execute(
                sa.text(
                    "INSERT INTO party (kind, display_name, email) "
                    "VALUES ('person', 'Bea', 'bea@example.org') RETURNING id"
                )
            ).scalar_one()
            conn.execute(
                sa.text(
                    "INSERT INTO bookings (space_slot_id, party_id, status, "
                    "payment_due_at, pending_since) "
                    "VALUES (:slot, :party, 'pending', now() + interval '1 hour', now())"
                ),
                {"slot": slot_id, "party": party_id},
            )

    def test_a_pending_row_blocks_a_second_active_row(self, upgraded):
        engine, slot_id, _ = upgraded
        with engine.begin() as conn:
            party_id = conn.execute(
                sa.text(
                    "INSERT INTO party (kind, display_name, email) "
                    "VALUES ('person', 'Cai', 'cai@example.org') RETURNING id"
                )
            ).scalar_one()
            conn.execute(
                sa.text(
                    "INSERT INTO bookings (space_slot_id, party_id, status) "
                    "VALUES (:slot, :party, 'pending')"
                ),
                {"slot": slot_id, "party": party_id},
            )
        with pytest.raises(sa.exc.IntegrityError):
            with engine.begin() as conn:
                conn.execute(
                    sa.text(
                        "INSERT INTO bookings (space_slot_id, party_id, status) "
                        "VALUES (:slot, :party, 'waitlisted')"
                    ),
                    {"slot": slot_id, "party": party_id},
                )

    @pytest.mark.parametrize(
        "table,assignment",
        [
            ("spaces", "payment_flow = 'other'"),
            ("spaces", "payment_methods = ARRAY['sepa']::varchar[]"),
            ("bookings", "refund_status = 'maybe'"),
            ("bookings", "status = 'held'"),
        ],
    )
    def test_the_database_refuses_values_outside_the_vocabulary(
        self, upgraded, table, assignment
    ):
        engine, _, _ = upgraded
        with pytest.raises(sa.exc.IntegrityError):
            with engine.begin() as conn:
                conn.execute(sa.text(f"UPDATE {table} SET {assignment}"))
