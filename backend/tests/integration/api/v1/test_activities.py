"""Integration tests for activity endpoints."""

from datetime import datetime, timedelta, timezone

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.activities.models import Activity, ActivityPrice
from app.domains.auth.models import User
from app.domains.persons.models import Person


def _create_user(db, role="admin", suffix=""):
    person = Person(first_name="Test", last_name="User", email=f"act-{role}{suffix}@test.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=f"act-{role}{suffix}@test.com",
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id, user.role)}


def _create_activity(db, created_by_id=None, **overrides):
    now = datetime.now(timezone.utc)
    defaults = {
        "name": "Test Activity",
        "slug": f"test-activity-{id(overrides)}",
        "starts_at": now + timedelta(days=10),
        "ends_at": now + timedelta(days=11),
        "registration_starts_at": now - timedelta(days=1),
        "registration_ends_at": now + timedelta(days=9),
        "max_participants": 50,
        "status": "draft",
        "is_active": True,
    }
    defaults.update(overrides)
    if created_by_id:
        defaults["created_by"] = created_by_id
    activity = Activity(**defaults)
    db.add(activity)
    db.flush()
    return activity


def _activity_payload(**overrides):
    now = datetime.now(timezone.utc)
    defaults = {
        "name": "Summer Camp",
        "starts_at": (now + timedelta(days=10)).isoformat(),
        "ends_at": (now + timedelta(days=11)).isoformat(),
        "registration_starts_at": (now - timedelta(days=1)).isoformat(),
        "registration_ends_at": (now + timedelta(days=9)).isoformat(),
        "max_participants": 50,
    }
    defaults.update(overrides)
    return defaults


class TestActivityCRUD:
    def test_create_activity(self, client, db):
        user = _create_user(db, "admin")
        client.cookies.update(_auth_cookie(user))

        response = client.post("/api/v1/activities/", json=_activity_payload())
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Summer Camp"
        assert data["slug"] == "summer-camp"
        assert data["status"] == "draft"

    def test_create_activity_requires_admin(self, client, db):
        user = _create_user(db, "member")
        client.cookies.update(_auth_cookie(user))

        response = client.post("/api/v1/activities/", json=_activity_payload())
        assert response.status_code == 403

    def test_list_activities_admin(self, client, db):
        user = _create_user(db, "admin")
        _create_activity(db, slug="draft-act", status="draft", created_by_id=user.id)
        _create_activity(db, slug="pub-act", status="published", created_by_id=user.id)
        client.cookies.update(_auth_cookie(user))

        response = client.get("/api/v1/activities/")
        assert response.status_code == 200
        data = response.json()
        statuses = {item["status"] for item in data["items"]}
        assert "draft" in statuses
        assert "published" in statuses

    def test_list_activities_member(self, client, db):
        admin = _create_user(db, "admin", suffix="-list-m")
        _create_activity(db, slug="draft-m", status="draft", created_by_id=admin.id)
        _create_activity(db, slug="pub-m", status="published", created_by_id=admin.id)
        member = _create_user(db, "member", suffix="-list")
        client.cookies.update(_auth_cookie(member))

        response = client.get("/api/v1/activities/")
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["status"] == "published"

    def test_list_activities_search(self, client, db):
        user = _create_user(db, "admin", suffix="-search")
        _create_activity(db, name="Yoga Class", slug="yoga-class", created_by_id=user.id)
        _create_activity(db, name="Swimming", slug="swimming", created_by_id=user.id)
        client.cookies.update(_auth_cookie(user))

        response = client.get("/api/v1/activities/", params={"search": "Yoga"})
        assert response.status_code == 200
        data = response.json()
        assert all("Yoga" in item["name"] for item in data["items"])

    def test_list_activities_filter_status(self, client, db):
        user = _create_user(db, "admin", suffix="-filter")
        _create_activity(db, slug="draft-f", status="draft", created_by_id=user.id)
        _create_activity(db, slug="pub-f", status="published", created_by_id=user.id)
        client.cookies.update(_auth_cookie(user))

        response = client.get("/api/v1/activities/", params={"status": "draft"})
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["status"] == "draft"

    def test_get_activity(self, client, db):
        user = _create_user(db, "admin", suffix="-get")
        activity = _create_activity(db, slug="get-act", created_by_id=user.id)
        client.cookies.update(_auth_cookie(user))

        response = client.get(f"/api/v1/activities/{activity.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == activity.id
        assert "modalities" in data
        assert "prices" in data

    def test_update_activity(self, client, db):
        user = _create_user(db, "admin", suffix="-upd")
        activity = _create_activity(db, slug="upd-act", created_by_id=user.id)
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            f"/api/v1/activities/{activity.id}",
            json={"name": "Updated Name", "description": "New desc"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "New desc"

    def test_delete_draft(self, client, db):
        user = _create_user(db, "admin", suffix="-del")
        activity = _create_activity(db, slug="del-act", status="draft", created_by_id=user.id)
        client.cookies.update(_auth_cookie(user))

        response = client.delete(f"/api/v1/activities/{activity.id}")
        assert response.status_code == 204

    def test_delete_published_fails(self, client, db):
        user = _create_user(db, "admin", suffix="-delpub")
        activity = _create_activity(db, slug="del-pub-act", status="published", created_by_id=user.id)
        client.cookies.update(_auth_cookie(user))

        response = client.delete(f"/api/v1/activities/{activity.id}")
        assert response.status_code == 400

    def test_slug_generation(self, client, db):
        user = _create_user(db, "admin", suffix="-slug")
        client.cookies.update(_auth_cookie(user))

        r1 = client.post("/api/v1/activities/", json=_activity_payload(name="Duplicate Name"))
        assert r1.status_code == 201
        assert r1.json()["slug"] == "duplicate-name"

        r2 = client.post("/api/v1/activities/", json=_activity_payload(name="Duplicate Name"))
        assert r2.status_code == 201
        assert r2.json()["slug"] == "duplicate-name-2"

    def test_date_validation(self, client, db):
        user = _create_user(db, "admin", suffix="-dateval")
        client.cookies.update(_auth_cookie(user))

        now = datetime.now(timezone.utc)
        payload = _activity_payload(
            starts_at=(now + timedelta(days=11)).isoformat(),
            ends_at=(now + timedelta(days=10)).isoformat(),
        )
        response = client.post("/api/v1/activities/", json=payload)
        assert response.status_code == 400


class TestActivityLifecycle:
    def test_publish_activity(self, client, db):
        user = _create_user(db, "admin", suffix="-pub")
        activity = _create_activity(db, slug="pub-lifecycle", status="draft", created_by_id=user.id)
        # Add a price so publish succeeds
        price = ActivityPrice(activity_id=activity.id, name="Standard", amount=10.0)
        db.add(price)
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.put(f"/api/v1/activities/{activity.id}/publish")
        assert response.status_code == 200
        assert response.json()["status"] == "published"

    def test_publish_without_price_fails(self, client, db):
        user = _create_user(db, "admin", suffix="-pubnp")
        activity = _create_activity(db, slug="pub-noprice", status="draft", created_by_id=user.id)
        client.cookies.update(_auth_cookie(user))

        response = client.put(f"/api/v1/activities/{activity.id}/publish")
        assert response.status_code == 400

    def test_archive_activity(self, client, db):
        user = _create_user(db, "admin", suffix="-arc")
        activity = _create_activity(db, slug="arc-lifecycle", status="published", created_by_id=user.id)
        client.cookies.update(_auth_cookie(user))

        response = client.put(f"/api/v1/activities/{activity.id}/archive")
        assert response.status_code == 200
        assert response.json()["status"] == "archived"

    def test_cancel_activity(self, client, db):
        user = _create_user(db, "admin", suffix="-cnc")
        activity = _create_activity(db, slug="cnc-lifecycle", status="published", created_by_id=user.id)
        client.cookies.update(_auth_cookie(user))

        response = client.put(f"/api/v1/activities/{activity.id}/cancel")
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"

    def test_cannot_publish_archived(self, client, db):
        user = _create_user(db, "admin", suffix="-arcpub")
        activity = _create_activity(db, slug="arcpub-lifecycle", status="archived", created_by_id=user.id)
        client.cookies.update(_auth_cookie(user))

        response = client.put(f"/api/v1/activities/{activity.id}/publish")
        assert response.status_code == 400
