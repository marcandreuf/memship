"""What a seat owes on payment, shown, and what the club owes back (#591)."""

from decimal import Decimal

import pytest

from app.domains.activities.registration_service import (
    admin_change_status,
    cancel_registration,
    register_member,
)
from app.domains.billing.models import Receipt
from app.domains.billing.seats import SeatError, mark_refund_returned
from app.domains.billing.service import mark_receipt_paid
from tests.integration.test_receipt_payment import _auth_cookie, _create_admin
from tests.integration.test_registration_billing import (
    _activity,
    _member,
    _receipts_for,
    membership_type,  # noqa: F401 — fixture
    org,  # noqa: F401 — fixture
)

PAY = "pay_to_confirm"


def _paid_seat(db, membership_type, suffix, flow=PAY):
    activity, price = _activity(db, payment_flow=flow)
    registration = register_member(
        db, activity, _member(db, membership_type, suffix), price.id
    )
    [receipt] = _receipts_for(db, registration)
    mark_receipt_paid(
        db,
        receipt,
        payment_method="stripe_checkout",
        stripe_payment_intent_id=f"pi_{suffix}",
    )
    return activity, registration, receipt


class TestTheListShowsWhoHasPaid:
    def test_a_pending_seat_carries_its_receipt_and_deadline(
        self, client, db, org, membership_type
    ):
        activity, price = _activity(db, payment_flow=PAY)
        registration = register_member(
            db, activity, _member(db, membership_type, "shown"), price.id
        )
        [receipt] = _receipts_for(db, registration)
        admin = _create_admin(db, "list-shown")

        items = client.get(
            f"/api/v1/activities/{activity.id}/registrations/",
            cookies=_auth_cookie(admin),
        ).json()["items"]

        [item] = items
        assert item["status"] == "pending"
        assert item["receipt_id"] == receipt.id
        assert item["receipt_status"] == "emitted"
        assert item["receipt_due_date"] == receipt.due_date.isoformat()
        assert item["refund_status"] == "none"

    def test_a_paid_seat_reads_paid(self, client, db, org, membership_type):
        activity, registration, _ = _paid_seat(db, membership_type, "paid-shown")
        admin = _create_admin(db, "list-paid")

        [item] = client.get(
            f"/api/v1/activities/{activity.id}/registrations/",
            cookies=_auth_cookie(admin),
        ).json()["items"]

        assert (item["status"], item["receipt_status"]) == ("confirmed", "paid")

    def test_the_csv_carries_payment_state(self, client, db, org, membership_type):
        activity, _, _ = _paid_seat(db, membership_type, "csv")
        admin = _create_admin(db, "csv")

        header, row = client.get(
            f"/api/v1/activities/{activity.id}/registrations/export.csv",
            cookies=_auth_cookie(admin),
        ).text.lstrip("﻿").splitlines()[:2]

        assert header.split(",")[-4:] == [
            "receipt_status", "payment_due_at", "refund_status", "late_payment_at"
        ]
        assert row.split(",")[-4] == "paid"


class TestCancellingAPaidSeat:
    @pytest.mark.parametrize("flow", ["legacy", PAY])
    def test_owes_the_payment_back(self, db, org, membership_type, flow):
        _, registration, receipt = _paid_seat(db, membership_type, f"owe-{flow}", flow)

        admin_change_status(db, registration, "cancelled")

        assert registration.refund_status == "due"
        assert receipt.status == "paid"

    def test_unless_the_organiser_keeps_it(self, db, org, membership_type):
        _, registration, _ = _paid_seat(db, membership_type, "keep")

        cancel_registration(db, registration, keep_payment=True)

        assert registration.refund_status == "none"

    def test_an_unpaid_seat_owes_nothing(self, db, org, membership_type):
        activity, price = _activity(db, payment_flow=PAY)
        registration = register_member(
            db, activity, _member(db, membership_type, "unpaid"), price.id
        )

        cancel_registration(db, registration)

        assert registration.refund_status == "none"

    def test_a_member_cannot_choose_to_keep_their_own_payment(
        self, client, db, org, membership_type
    ):
        from app.core.security.jwt import create_access_token
        from app.core.security.password import hash_password
        from app.domains.auth.models import User

        activity, registration, _ = _paid_seat(db, membership_type, "self", "legacy")
        activity.allow_self_cancellation = True
        member = registration.member
        user = User(
            party_id=member.party_id,
            email=member.person.email,
            password_hash=hash_password("password123"),
            role="member",
            is_active=True,
        )
        db.add(user)
        db.flush()
        member.user_id = user.id
        db.flush()

        resp = client.request(
            "DELETE",
            f"/api/v1/registrations/{registration.id}",
            json={"keep_payment": True},
            cookies={"access_token": create_access_token(user.id)},
        )

        assert resp.status_code == 204, resp.text
        db.refresh(registration)
        assert registration.refund_status == "due"


class TestTheRefundList:
    def test_lists_what_finds_the_money(self, client, db, org, membership_type):
        _, registration, receipt = _paid_seat(db, membership_type, "listed")
        cancel_registration(db, registration)
        admin = _create_admin(db, "refunds")

        items = client.get(
            "/api/v1/registrations/refunds", cookies=_auth_cookie(admin)
        ).json()["items"]

        [item] = [i for i in items if i["registration_id"] == registration.id]
        assert item["receipt_number"] == receipt.receipt_number
        assert Decimal(str(item["amount"])) == receipt.total_amount
        assert item["payment_method"] == "stripe_checkout"
        assert item["gateway_reference"] == "pi_listed"

    def test_marking_it_returned_moves_it_to_the_returned_list(
        self, client, db, org, membership_type
    ):
        _, registration, _ = _paid_seat(db, membership_type, "returned")
        cancel_registration(db, registration)
        admin = _create_admin(db, "returned")

        resp = client.post(
            f"/api/v1/registrations/{registration.id}/refund-returned",
            cookies=_auth_cookie(admin),
        )

        assert resp.status_code == 200, resp.text
        db.refresh(registration)
        assert registration.refund_status == "returned"
        assert registration.refund_returned_by == admin.id
        assert registration.refund_returned_at is not None
        due = client.get(
            "/api/v1/registrations/refunds", cookies=_auth_cookie(admin)
        ).json()["items"]
        returned = client.get(
            "/api/v1/registrations/refunds?refund_status=returned",
            cookies=_auth_cookie(admin),
        ).json()["items"]
        assert registration.id not in [i["registration_id"] for i in due]
        assert registration.id in [i["registration_id"] for i in returned]


class TestMarkRefundReturned:
    def test_only_a_refund_that_is_due(self, db, org, membership_type):
        _, registration, _ = _paid_seat(db, membership_type, "not-due")

        with pytest.raises(SeatError):
            mark_refund_returned(db, registration, None)

    def test_takes_a_credit_note_issued_to_the_same_member(
        self, db, org, membership_type
    ):
        _, registration, receipt = _paid_seat(db, membership_type, "note")
        cancel_registration(db, registration)
        note = Receipt(
            receipt_number="ABONO-591-1",
            document_type="credit_note",
            rectifies_receipt_id=receipt.id,
            party_id=registration.party_id,
            origin="activity",
            description="Refund",
            base_amount=-receipt.base_amount,
            vat_rate=receipt.vat_rate,
            vat_amount=-receipt.vat_amount,
            total_amount=-receipt.total_amount,
            status="emitted",
            emission_date=receipt.emission_date,
        )
        db.add(note)
        db.flush()

        mark_refund_returned(db, registration, None, note.id)

        assert registration.refund_credit_note_id == note.id

    def test_refuses_a_document_that_is_not_that_members_credit_note(
        self, db, org, membership_type
    ):
        _, registration, receipt = _paid_seat(db, membership_type, "wrong-note")
        cancel_registration(db, registration)

        with pytest.raises(SeatError):
            mark_refund_returned(db, registration, None, receipt.id)
