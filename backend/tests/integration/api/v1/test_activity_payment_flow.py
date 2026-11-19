"""The payment flow, accepted methods and auto-cancel override on an activity."""

import pytest

from tests.integration.api.v1.test_activities import (
    _activity_payload,
    _auth_cookie,
    _create_activity,
    _create_user,
)


class TestPaymentFlow:
    def test_a_new_activity_uses_the_new_flow(self, client, db):
        client.cookies.update(_auth_cookie(_create_user(db, "admin", "-flow-new")))

        data = client.post("/api/v1/activities/", json=_activity_payload()).json()

        assert data["payment_flow"] == "pay_to_confirm"
        assert data["payment_methods"] == []
        assert data["auto_cancel_enabled"] is None
        assert data["auto_cancel_hours"] is None

    def test_the_flow_cannot_be_chosen_at_creation(self, client, db):
        client.cookies.update(_auth_cookie(_create_user(db, "admin", "-flow-create")))

        data = client.post(
            "/api/v1/activities/", json=_activity_payload(payment_flow="legacy")
        ).json()

        assert data["payment_flow"] == "pay_to_confirm"

    def test_the_flow_cannot_be_changed_afterwards(self, client, db):
        admin = _create_user(db, "admin", "-flow-update")
        activity = _create_activity(
            db, slug="flow-fixed", payment_flow="legacy", created_by_id=admin.id
        )
        client.cookies.update(_auth_cookie(admin))

        response = client.put(
            f"/api/v1/activities/{activity.id}",
            json={"payment_flow": "pay_to_confirm", "name": "Renamed"},
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Renamed"
        assert response.json()["payment_flow"] == "legacy"

    def test_the_list_carries_the_flow(self, client, db):
        admin = _create_user(db, "admin", "-flow-list")
        _create_activity(
            db, slug="flow-list", payment_flow="legacy", created_by_id=admin.id
        )
        client.cookies.update(_auth_cookie(admin))

        items = client.get("/api/v1/activities/").json()["items"]

        assert {i["slug"]: i["payment_flow"] for i in items}["flow-list"] == "legacy"

    def test_methods_and_the_auto_cancel_override_are_saved(self, client, db):
        client.cookies.update(_auth_cookie(_create_user(db, "admin", "-flow-methods")))

        data = client.post(
            "/api/v1/activities/",
            json=_activity_payload(
                payment_methods=["card", "transfer", "card"],
                auto_cancel_enabled=False,
                auto_cancel_hours=48,
            ),
        ).json()

        assert data["payment_methods"] == ["card", "transfer"]
        assert data["auto_cancel_enabled"] is False
        assert data["auto_cancel_hours"] == 48

    @pytest.mark.parametrize(
        "extra",
        [
            {"payment_methods": ["direct_debit"]},
            {"payment_methods": ["sepa"]},
            {"auto_cancel_hours": 0},
            {"auto_cancel_hours": 8761},
        ],
    )
    def test_values_outside_the_vocabulary_are_refused(self, client, db, extra):
        client.cookies.update(_auth_cookie(_create_user(db, "admin", "-flow-bad")))

        response = client.post("/api/v1/activities/", json=_activity_payload(**extra))

        assert response.status_code == 422

    def test_methods_cannot_be_nulled_on_update(self, client, db):
        admin = _create_user(db, "admin", "-flow-null")
        activity = _create_activity(db, slug="flow-null", created_by_id=admin.id)
        client.cookies.update(_auth_cookie(admin))

        response = client.put(
            f"/api/v1/activities/{activity.id}", json={"payment_methods": None}
        )

        assert response.status_code == 422
