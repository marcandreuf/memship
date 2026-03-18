"""Integration tests for activity modality endpoints."""

from datetime import datetime, timedelta, timezone

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.activities.models import Activity, ActivityModality
from app.domains.auth.models import User
from app.domains.persons.models import Person


def _create_user(db, role="admin", suffix=""):
    person = Person(first_name="Test", last_name="User", email=f"mod-{role}{suffix}@test.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=f"mod-{role}{suffix}@test.com",
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id, user.role)}


def _create_activity(db, created_by_id, slug="mod-test-act"):
    now = datetime.now(timezone.utc)
    activity = Activity(
        name="Modality Test Activity",
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


class TestModalityCRUD:
    def test_create_modality(self, client, db):
        user = _create_user(db, "admin", suffix="-mc")
        activity = _create_activity(db, user.id, slug="mod-create")
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/modalities/",
            json={"name": "Morning Session", "description": "8am-12pm"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Morning Session"
        assert data["activity_id"] == activity.id

    def test_list_modalities(self, client, db):
        user = _create_user(db, "admin", suffix="-ml")
        activity = _create_activity(db, user.id, slug="mod-list")
        db.add(ActivityModality(activity_id=activity.id, name="Session A"))
        db.add(ActivityModality(activity_id=activity.id, name="Session B"))
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.get(f"/api/v1/activities/{activity.id}/modalities/")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_update_modality(self, client, db):
        user = _create_user(db, "admin", suffix="-mu")
        activity = _create_activity(db, user.id, slug="mod-update")
        modality = ActivityModality(activity_id=activity.id, name="Old Name")
        db.add(modality)
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            f"/api/v1/activities/{activity.id}/modalities/{modality.id}",
            json={"name": "New Name"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "New Name"

    def test_delete_modality(self, client, db):
        user = _create_user(db, "admin", suffix="-md")
        activity = _create_activity(db, user.id, slug="mod-delete")
        modality = ActivityModality(activity_id=activity.id, name="To Delete")
        db.add(modality)
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.delete(
            f"/api/v1/activities/{activity.id}/modalities/{modality.id}"
        )
        assert response.status_code == 204

    def test_unique_name_per_activity(self, client, db):
        user = _create_user(db, "admin", suffix="-mdup")
        activity = _create_activity(db, user.id, slug="mod-dup")
        db.add(ActivityModality(activity_id=activity.id, name="Duplicate"))
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/modalities/",
            json={"name": "Duplicate"},
        )
        assert response.status_code == 409
