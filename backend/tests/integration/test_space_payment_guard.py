"""A space can only charge for a booking in ways that hold together (#603).

A pay-to-confirm space releases every booking left unpaid at its deadline,
auto-cancel or not. So a space that charges must accept a way to pay the club
can take, and the mails that tell a member their booking is held, about to go
and gone must be on, and stay on while such a space exists. A space may move
from legacy to pay-to-confirm, never back.
"""

from datetime import time

import pytest

from app.domains.billing.seats import BOOKING_SEAT_TEMPLATES
from app.domains.bookings import service
from app.domains.bookings.models import Booking, Space
from app.domains.bookings.schemas import SpaceSlotCreate
from tests.integration.test_bookings_service import _member, _org
from tests.integration.test_pay_to_confirm_guard import _switch
from tests.integration.test_receipt_payment import _auth_cookie, _create_admin
from tests.integration.test_space_pay_to_confirm_booking import _receipts, _slot

SPACE = {"name": "Court", "open_time": "08:00", "close_time": "22:00"}


def _club(db, mails_on=True):
    org = _org(db)
    _switch(org, BOOKING_SEAT_TEMPLATES, enabled=mails_on)
    db.flush()
    return org


def _post(client, db, suffix, **fields):
    return client.post(
        "/api/v1/spaces",
        json={**SPACE, **fields},
        cookies=_auth_cookie(_create_admin(db, f"space-guard-{suffix}")),
    )


class TestCreatingASpaceThatCharges:
    def test_needs_a_way_to_pay(self, client, db):
        _club(db)

        resp = _post(client, db, "no-methods", price=10)

        assert resp.status_code == 422, resp.text
        assert resp.json()["detail"]["code"] == "space_payment_methods_required"

    def test_needs_ways_the_club_can_take(self, client, db):
        _club(db)

        resp = _post(client, db, "card", price=10, payment_methods=["card"])

        assert resp.status_code == 422, resp.text
        assert resp.json()["detail"]["code"] == "payment_methods_unavailable"
        assert resp.json()["detail"]["methods"] == ["card"]

    def test_needs_the_mails_that_warn_its_holders(self, client, db):
        _club(db, mails_on=False)

        resp = _post(client, db, "mails", price=10, payment_methods=["cash"])

        assert resp.status_code == 422, resp.text
        assert resp.json()["detail"]["code"] == "space_payment_needs_emails"
        assert resp.json()["detail"]["templates"] == list(BOOKING_SEAT_TEMPLATES)

    def test_is_created_pay_to_confirm_when_all_hold(self, client, db):
        _club(db)

        resp = _post(client, db, "ok", price=10, payment_methods=["cash"])

        assert resp.status_code == 201, resp.text
        assert resp.json()["payment_flow"] == "pay_to_confirm"
        assert resp.json()["payment_methods"] == ["cash"]

    def test_a_free_space_needs_none_of_it(self, client, db):
        _club(db, mails_on=False)

        assert _post(client, db, "free").status_code == 201

    def test_a_paid_slot_in_a_free_space_counts(self, db):
        _club(db)
        space = Space(name="Room", open_time=time(8), close_time=time(22), is_active=True)
        db.add(space)
        db.flush()

        with pytest.raises(service.SpacePaymentMethodsRequired):
            service.create_slot(
                db,
                space,
                SpaceSlotCreate(
                    slot_date=_slot(db, space).slot_date,
                    start_time=time(12),
                    end_time=time(13),
                    price=5,
                ),
            )


class TestTheLegacyFlow:
    def _legacy(self, db):
        space = Space(
            name="Old court",
            open_time=time(8),
            close_time=time(22),
            is_active=True,
            price=10,
            payment_flow="legacy",
        )
        db.add(space)
        db.flush()
        return space

    def test_may_be_switched_to_pay_to_confirm(self, client, db):
        _club(db)
        space = self._legacy(db)
        admin = _create_admin(db, "space-switch")

        resp = client.put(
            f"/api/v1/spaces/{space.id}",
            json={"payment_flow": "pay_to_confirm", "payment_methods": ["cash"]},
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["payment_flow"] == "pay_to_confirm"

    def test_the_switch_leaves_bookings_already_made_as_they_were(self, db):
        _club(db)
        space = self._legacy(db)
        slot = _slot(db, space)
        before = service.create_booking(db, _member(db, 1), slot.id)
        assert before.status == "booked"

        service.update_space(
            db,
            space,
            service.SpaceUpdate(payment_flow="pay_to_confirm", payment_methods=["cash"]),
        )

        assert before.status == "booked"
        [receipt] = _receipts(db, before)
        assert receipt.is_batchable is True
        slot.capacity = 2
        after = service.create_booking(db, _member(db, 2), slot.id)
        assert after.status == "pending"

    def test_the_switch_is_refused_while_the_mails_are_off(self, client, db):
        _club(db, mails_on=False)
        space = self._legacy(db)
        admin = _create_admin(db, "space-switch-mails")

        resp = client.put(
            f"/api/v1/spaces/{space.id}",
            json={"payment_flow": "pay_to_confirm", "payment_methods": ["cash"]},
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 422, resp.text
        assert resp.json()["detail"]["code"] == "space_payment_needs_emails"
        db.refresh(space)
        assert space.payment_flow == "legacy"

    def test_cannot_be_switched_back(self, client, db):
        _club(db)
        resp = _post(client, db, "back", price=10, payment_methods=["cash"])
        admin = _create_admin(db, "space-switch-back")

        back = client.put(
            f"/api/v1/spaces/{resp.json()['id']}",
            json={"payment_flow": "legacy"},
            cookies=_auth_cookie(admin),
        )

        assert back.status_code == 422


class TestTheMailsStayOn:
    @pytest.mark.parametrize("key", BOOKING_SEAT_TEMPLATES)
    def test_while_a_space_charges(self, client, db, key):
        _club(db)
        assert _post(client, db, f"stay-{key}", price=10, payment_methods=["cash"]).status_code == 201
        admin = _create_admin(db, f"mails-stay-{key}")

        resp = client.put(
            "/api/v1/settings/communications",
            json={"templates": {key: False}},
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 422, resp.text
        assert resp.json()["detail"] == {
            "code": "templates_needed_by_paid_spaces",
            "templates": [key],
        }

    def test_but_not_for_free_or_legacy_spaces(self, client, db):
        _club(db)
        assert _post(client, db, "free-only").status_code == 201
        admin = _create_admin(db, "mails-free")

        resp = client.put(
            "/api/v1/settings/communications",
            json={"templates": {"booking_pending_payment": False}},
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 200, resp.text
        assert db.query(Booking).count() == 0
