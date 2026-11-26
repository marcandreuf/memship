"""The cancellation policy of a paid seat, for activities and spaces (#604).

A member who cancels inside the deadline has the payment marked refund due. Past
it the club chose, per activity and per space, between refusing and releasing the
seat while keeping the money. An administrator chooses at the moment, and a seat
that was never paid has nothing to return whatever the policy says.
"""

import pytest

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.activities.registration_service import (
    cancel_registration,
    register_member,
    self_cancellation_policy,
)
from app.domains.auth.models import User
from app.domains.billing.service import mark_receipt_paid
from app.domains.bookings import service
from tests.integration.test_bookings_service import _org
from tests.integration.test_registration_billing import (
    _activity,
    _member,
    _receipts_for,
    membership_type,  # noqa: F401 — fixture
    org,  # noqa: F401 — fixture
)
from tests.integration.test_registration_refunds import _paid_seat
from tests.integration.test_space_pay_to_confirm_payment import _admin_cancel, _pending

WEEK = 7 * 24 * 60  # the activities start in ten days, the slots in three


def _policy(activity, **fields):
    activity.allow_self_cancellation = True
    for key, value in fields.items():
        setattr(activity, key, value)


class TestAnActivity:
    def test_inside_the_deadline_the_payment_is_owed_back(
        self, db, org, membership_type
    ):
        activity, registration, _ = _paid_seat(db, membership_type, "in-time")
        _policy(activity, self_cancellation_deadline_minutes=60)

        error, keep = self_cancellation_policy(activity, registration)
        cancel_registration(db, registration, keep_payment=keep)

        assert (error, keep) == (None, False)
        assert registration.refund_status == "due"

    def test_no_deadline_means_always_refundable(self, db, org, membership_type):
        activity, registration, _ = _paid_seat(db, membership_type, "no-limit")
        _policy(activity, self_cancellation_deadline_minutes=None)

        assert self_cancellation_policy(activity, registration) == (None, False)

    def test_past_it_the_default_refuses(self, db, org, membership_type):
        activity, registration, _ = _paid_seat(db, membership_type, "blocked")
        _policy(activity, self_cancellation_deadline_minutes=20 * 24 * 60)

        error, keep = self_cancellation_policy(activity, registration)

        assert "deadline" in error
        assert keep is False

    def test_past_it_the_club_may_keep_the_payment(self, db, org, membership_type):
        activity, registration, receipt = _paid_seat(db, membership_type, "kept")
        _policy(
            activity,
            self_cancellation_deadline_minutes=20 * 24 * 60,
            late_cancellation_mode="allow_no_refund",
        )

        error, keep = self_cancellation_policy(activity, registration)
        cancel_registration(db, registration, keep_payment=keep)

        assert error is None
        assert registration.status == "cancelled"
        assert registration.refund_status == "none"
        assert receipt.status == "paid"

    def test_a_deadline_in_minutes_is_honoured(self, db, org, membership_type):
        activity, registration, _ = _paid_seat(db, membership_type, "minutes")
        # The activity starts in ten days. A deadline of ten days less thirty
        # minutes falls half an hour from now; ten days and thirty, half an hour ago.
        _policy(
            activity,
            self_cancellation_deadline_minutes=10 * 24 * 60 - 30,
            late_cancellation_mode="allow_no_refund",
        )
        assert self_cancellation_policy(activity, registration) == (None, False)

        _policy(activity, self_cancellation_deadline_minutes=10 * 24 * 60 + 30)
        assert self_cancellation_policy(activity, registration) == (None, True)

    def test_an_unpaid_seat_owes_nothing_either_way(self, db, org, membership_type):
        activity, price = _activity(db, payment_flow="pay_to_confirm")
        registration = register_member(
            db, activity, _member(db, membership_type, "unpaid-late"), price.id
        )
        _policy(
            activity,
            self_cancellation_deadline_minutes=20 * 24 * 60,
            late_cancellation_mode="allow_no_refund",
        )

        _, keep = self_cancellation_policy(activity, registration)
        cancel_registration(db, registration, keep_payment=keep)

        assert registration.refund_status == "none"
        assert _receipts_for(db, registration)[0].status == "cancelled"

    def test_through_the_api_a_late_member_loses_the_payment(
        self, client, db, org, membership_type
    ):
        activity, registration, _ = _paid_seat(db, membership_type, "api-late")
        _policy(
            activity,
            self_cancellation_deadline_minutes=20 * 24 * 60,
            late_cancellation_mode="allow_no_refund",
        )
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

        resp = client.delete(
            f"/api/v1/registrations/{registration.id}",
            cookies={"access_token": create_access_token(user.id)},
        )

        assert resp.status_code == 204, resp.text
        db.refresh(registration)
        assert registration.refund_status == "none"

    def test_the_mode_is_validated(self, client, db, org):
        from pydantic import ValidationError

        from app.domains.activities.schemas import ActivityUpdate

        with pytest.raises(ValidationError):
            ActivityUpdate(late_cancellation_mode="keep")
        with pytest.raises(ValidationError):
            ActivityUpdate(late_cancellation_mode=None)


class TestASpace:
    def test_inside_the_deadline_the_payment_is_owed_back(self, db):
        _org(db)
        _, booking, _ = _paid_in(db, cancellation_deadline_minutes=60)

        service.cancel_booking(db, booking, cancelled_by_user_id=None, is_admin=False)

        assert booking.refund_status == "due"

    def test_past_it_the_default_refuses(self, db):
        _org(db)
        _, booking, _ = _paid_in(db, cancellation_deadline_minutes=WEEK)

        with pytest.raises(service.CancellationTooLate):
            service.cancel_booking(
                db, booking, cancelled_by_user_id=None, is_admin=False
            )

    def test_past_it_the_club_may_keep_the_payment(self, db):
        _org(db)
        _, booking, receipt = _paid_in(
            db,
            cancellation_deadline_minutes=WEEK,
            late_cancellation_mode="allow_no_refund",
        )

        service.cancel_booking(db, booking, cancelled_by_user_id=None, is_admin=False)

        assert booking.status == "cancelled"
        assert booking.refund_status == "none"
        assert receipt.status == "paid"

    def test_the_list_says_whether_cancelling_costs_the_payment(self, db):
        _org(db)
        _, booking, _ = _paid_in(
            db,
            cancellation_deadline_minutes=WEEK,
            late_cancellation_mode="allow_no_refund",
        )

        [row] = service.my_bookings(db, booking.party_id, scope="upcoming")

        assert (row["can_cancel"], row["cancel_refundable"]) == (True, False)

    def test_the_space_deadline_beats_the_clubs(self, db):
        _org(db, booking_cancellation_deadline_minutes=0)
        _, booking, _ = _paid_in(db, cancellation_deadline_minutes=WEEK)

        with pytest.raises(service.CancellationTooLate):
            service.cancel_booking(
                db, booking, cancelled_by_user_id=None, is_admin=False
            )

    def test_without_its_own_deadline_it_inherits_the_clubs(self, db):
        _org(db, booking_cancellation_deadline_minutes=WEEK)
        _, booking, _ = _paid_in(db, cancellation_deadline_minutes=None)

        with pytest.raises(service.CancellationTooLate):
            service.cancel_booking(
                db, booking, cancelled_by_user_id=None, is_admin=False
            )

    @pytest.mark.parametrize("keep", [False, True])
    def test_an_administrator_chooses_whatever_the_policy(self, db, keep):
        _org(db)
        _, booking, _ = _paid_in(
            db,
            cancellation_deadline_minutes=WEEK,
            late_cancellation_mode="allow_no_refund",
        )

        _admin_cancel(db, booking, keep_payment=keep)

        assert booking.refund_status == ("none" if keep else "due")


def _paid_in(db, **space_kwargs):
    slot, booking, receipt = _pending(db, **space_kwargs)
    mark_receipt_paid(db, receipt, payment_method="cash")
    return slot, booking, receipt


class TestTheConfirmationMail:
    @pytest.mark.parametrize(
        "mode, price, keeps",
        [
            ("allow_no_refund", 12, True),
            ("allow_no_refund", None, False),  # free: nothing to keep
            ("block", 12, False),
        ],
    )
    def test_says_the_payment_is_kept_only_when_it_is(self, db, mode, price, keeps):
        from tests.integration.test_space_pay_to_confirm_booking import _slot, _space

        _org(db)
        space = _space(db, price=price, late_cancellation_mode=mode)
        slot = _slot(db, space)

        terms = service._cancellation_terms(db, space, slot)

        assert terms["late_cancellation_keeps_payment"] is keeps
        assert terms["cancellation_deadline_minutes"] == 1440
