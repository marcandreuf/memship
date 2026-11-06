"""Integration tests for activity price endpoints."""

from datetime import datetime, timedelta, timezone

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.activities.models import Activity, ActivityModality, ActivityPrice
from app.domains.auth.models import User
from app.domains.persons.models import Person


def _create_user(db, role="admin", suffix=""):
    person = Person(first_name="Test", last_name="User", email=f"price-{role}{suffix}@examplee6e3b1.com")
    db.add(person)
    db.flush()
    user = User(
        party_id=person.party_id,
        email=f"price-{role}{suffix}@examplee6e3b1.com",
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id)}


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

    def test_modality_id_zero_is_refused_on_update(self, client, db):
        """0 is an emptied form field, not a modality, and must not reach the FK.

        The form sent 0 for "no modality", the schema accepted it as a valid
        int, and PostgreSQL refused it against ``activity_modalities`` — so a
        price edit answered 500 instead of 422 (#542).
        """
        user = _create_user(db, "admin", suffix="-pz")
        activity = _create_activity(db, user.id, slug="price-zero-mod")
        price = ActivityPrice(activity_id=activity.id, name="Price", amount=10.0)
        db.add(price)
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            f"/api/v1/activities/{activity.id}/prices/{price.id}",
            json={"name": "Price", "amount": 10.0, "modality_id": 0},
        )
        assert response.status_code == 422

    def test_modality_id_zero_is_refused_on_create(self, client, db):
        user = _create_user(db, "admin", suffix="-pzc")
        activity = _create_activity(db, user.id, slug="price-zero-mod-create")
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/prices/",
            json={"name": "Price", "amount": 10.0, "modality_id": 0},
        )
        assert response.status_code == 422

    def test_modality_id_null_still_means_no_modality(self, client, db):
        """The bound must not break the legitimate "no modality" case."""
        user = _create_user(db, "admin", suffix="-pn")
        activity = _create_activity(db, user.id, slug="price-null-mod")
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/prices/",
            json={"name": "Price", "amount": 10.0, "modality_id": None},
        )
        assert response.status_code == 201
        assert response.json()["modality_id"] is None

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
