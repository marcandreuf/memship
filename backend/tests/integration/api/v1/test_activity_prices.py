"""Integration tests for activity price endpoints."""

from datetime import datetime, timedelta, timezone

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.activities.models import Activity, ActivityModality, ActivityPrice
from app.domains.auth.models import User
from app.domains.persons.models import Person


def _create_user(db, role="admin", suffix=""):
    person = Person(first_name="Test", last_name="User", email=f"price-{role}{suffix}@test.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=f"price-{role}{suffix}@test.com",
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id, user.role)}


def _create_activity(db, created_by_id, slug="price-test-act"):
    now = datetime.now(timezone.utc)
    activity = Activity(
        name="Price Test Activity",
        slug=slug,
        starts_at=now + timedelta(days=10),
        ends_at=now + timedelta(days=11),
        registration_starts_at=now - timedelta(days=1),
        registration_ends_at=now + timedelta(days=9),
        max_participants=50,
        status="draft",
        is_active=True,
        created_by=created_by_id,
    )
    db.add(activity)
    db.flush()
    return activity


class TestPriceCRUD:
    def test_create_price_activity_level(self, client, db):
        user = _create_user(db, "admin", suffix="-pc")
        activity = _create_activity(db, user.id, slug="price-create")
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/prices/",
            json={"name": "Standard", "amount": 25.50},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Standard"
        assert data["amount"] == 25.50
        assert data["modality_id"] is None
        assert data["activity_id"] == activity.id

    def test_create_price_modality_level(self, client, db):
        user = _create_user(db, "admin", suffix="-pm")
        activity = _create_activity(db, user.id, slug="price-mod")
        modality = ActivityModality(activity_id=activity.id, name="Morning")
        db.add(modality)
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/prices/",
            json={"name": "Morning Price", "amount": 30.00, "modality_id": modality.id},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["modality_id"] == modality.id

    def test_list_prices(self, client, db):
        user = _create_user(db, "admin", suffix="-pl")
        activity = _create_activity(db, user.id, slug="price-list")
        db.add(ActivityPrice(activity_id=activity.id, name="Price A", amount=10.0))
        db.add(ActivityPrice(activity_id=activity.id, name="Price B", amount=20.0))
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.get(f"/api/v1/activities/{activity.id}/prices/")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_update_price(self, client, db):
        user = _create_user(db, "admin", suffix="-pu")
        activity = _create_activity(db, user.id, slug="price-update")
        price = ActivityPrice(activity_id=activity.id, name="Old Price", amount=10.0)
        db.add(price)
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            f"/api/v1/activities/{activity.id}/prices/{price.id}",
            json={"name": "New Price", "amount": 15.0},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Price"
        assert data["amount"] == 15.0

    def test_delete_price(self, client, db):
        user = _create_user(db, "admin", suffix="-pd")
        activity = _create_activity(db, user.id, slug="price-delete")
        price = ActivityPrice(activity_id=activity.id, name="To Delete", amount=5.0)
        db.add(price)
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.delete(
            f"/api/v1/activities/{activity.id}/prices/{price.id}"
        )
        assert response.status_code == 204
