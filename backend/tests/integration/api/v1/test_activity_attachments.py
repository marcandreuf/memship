"""Integration tests for activity attachment type endpoints and file upload."""

import io
from datetime import datetime, timedelta, timezone

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.activities.models import (
    Activity, ActivityAttachmentType, ActivityPrice, Registration,
)
from app.domains.auth.models import User
from app.domains.members.models import Member, MembershipType
from app.domains.persons.models import Person


def _create_user(db, role="admin", suffix=""):
    person = Person(first_name="Att", last_name="User", email=f"att-{role}{suffix}@test.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id, email=f"att-{role}{suffix}@test.com",
        password_hash=hash_password("password123"), role=role, is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _create_member_with_user(db, suffix=""):
    person = Person(
        first_name="Member", last_name=f"Att{suffix}",
        email=f"member-att{suffix}@test.com",
    )
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id, email=f"member-att{suffix}@test.com",
        password_hash=hash_password("password123"), role="member", is_active=True,
    )
    db.add(user)
    db.flush()
    existing = db.query(MembershipType).filter(MembershipType.slug == f"gen-att{suffix}").first()
    if not existing:
        existing = MembershipType(name=f"GenAtt{suffix}", slug=f"gen-att{suffix}", is_active=True)
        db.add(existing)
        db.flush()
    member = Member(
        person_id=person.id, user_id=user.id, membership_type_id=existing.id,
        member_number=f"MA{suffix}-{user.id}", status="active",
    )
    db.add(member)
    db.flush()
    return user, member


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id, user.role)}


def _create_published_activity(db, admin_id=None, **overrides):
    now = datetime.now(timezone.utc)
    defaults = {
        "name": "Attach Test Activity",
        "slug": f"att-test-{id(overrides)}",
        "starts_at": now + timedelta(days=10),
        "ends_at": now + timedelta(days=11),
        "registration_starts_at": now - timedelta(days=1),
        "registration_ends_at": now + timedelta(days=9),
        "max_participants": 50,
        "status": "published",
        "is_active": True,
        "features": {},
    }
    defaults.update(overrides)
    if admin_id:
        defaults["created_by"] = admin_id
    activity = Activity(**defaults)
    db.add(activity)
    db.flush()
    price = ActivityPrice(
        activity_id=activity.id, name="Standard", amount=50.00,
        is_default=True, is_active=True,
    )
    db.add(price)
    db.flush()
    return activity, price


class TestAttachmentTypeCRUD:
    def test_create_attachment_type(self, client, db):
        admin = _create_user(db, "admin", suffix="-at1")
        activity, _ = _create_published_activity(db, admin.id)
        client.cookies.update(_auth_cookie(admin))

        response = client.post(
            f"/api/v1/activities/{activity.id}/attachment-types/",
            json={
                "name": "Medical Certificate",
                "description": "Required medical clearance",
                "allowed_extensions": ["pdf", "jpg", "png"],
                "max_file_size_mb": 5,
                "is_mandatory": True,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Medical Certificate"
        assert data["allowed_extensions"] == ["pdf", "jpg", "png"]
        assert data["is_mandatory"] is True

    def test_list_attachment_types(self, client, db):
        admin = _create_user(db, "admin", suffix="-at2")
        user, _ = _create_member_with_user(db, suffix="-at2")
        activity, _ = _create_published_activity(db, admin.id)
        att_type = ActivityAttachmentType(
            activity_id=activity.id, name="ID Card",
            allowed_extensions=["pdf"], is_mandatory=True, is_active=True,
        )
        db.add(att_type)
        db.flush()

        # Members can list attachment types
        client.cookies.update(_auth_cookie(user))
        response = client.get(f"/api/v1/activities/{activity.id}/attachment-types/")
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_update_attachment_type(self, client, db):
        admin = _create_user(db, "admin", suffix="-at3")
        activity, _ = _create_published_activity(db, admin.id)
        att_type = ActivityAttachmentType(
            activity_id=activity.id, name="Old Name",
            allowed_extensions=["pdf"], is_mandatory=True, is_active=True,
        )
        db.add(att_type)
        db.flush()

        client.cookies.update(_auth_cookie(admin))
        response = client.put(
            f"/api/v1/activities/{activity.id}/attachment-types/{att_type.id}",
            json={"name": "Updated Name", "max_file_size_mb": 10},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"
        assert response.json()["max_file_size_mb"] == 10

    def test_delete_attachment_type(self, client, db):
        admin = _create_user(db, "admin", suffix="-at4")
        activity, _ = _create_published_activity(db, admin.id)
        att_type = ActivityAttachmentType(
            activity_id=activity.id, name="Delete Me",
            allowed_extensions=[], is_mandatory=False, is_active=True,
        )
        db.add(att_type)
        db.flush()

        client.cookies.update(_auth_cookie(admin))
        response = client.delete(
            f"/api/v1/activities/{activity.id}/attachment-types/{att_type.id}"
        )
        assert response.status_code == 204

    def test_member_cannot_create_attachment_type(self, client, db):
        admin = _create_user(db, "admin", suffix="-at5")
        user, _ = _create_member_with_user(db, suffix="-at5")
        activity, _ = _create_published_activity(db, admin.id)

        client.cookies.update(_auth_cookie(user))
        response = client.post(
            f"/api/v1/activities/{activity.id}/attachment-types/",
            json={"name": "Sneaky", "allowed_extensions": ["pdf"]},
        )
        assert response.status_code == 403


class TestFileUpload:
    def test_upload_attachment(self, client, db):
        admin = _create_user(db, "admin", suffix="-fu1")
        user, member = _create_member_with_user(db, suffix="-fu1")
        activity, price = _create_published_activity(db, admin.id)
        att_type = ActivityAttachmentType(
            activity_id=activity.id, name="Medical Cert",
            allowed_extensions=["pdf", "txt"], max_file_size_mb=5,
            is_mandatory=True, is_active=True,
        )
        db.add(att_type)
        db.flush()

        # Create a registration first
        reg = Registration(
            activity_id=activity.id, member_id=member.id,
            price_id=price.id, status="confirmed",
        )
        db.add(reg)
        db.flush()

        client.cookies.update(_auth_cookie(user))
        file_content = b"This is a test file content"
        response = client.post(
            f"/api/v1/registrations/{reg.id}/attachments?attachment_type_id={att_type.id}",
            files={"file": ("medical_cert.txt", io.BytesIO(file_content), "text/plain")},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["file_name"] == "medical_cert.txt"
        assert data["file_size"] == len(file_content)
        assert data["attachment_type_id"] == att_type.id

    def test_upload_wrong_extension_rejected(self, client, db):
        admin = _create_user(db, "admin", suffix="-fu2")
        user, member = _create_member_with_user(db, suffix="-fu2")
        activity, price = _create_published_activity(db, admin.id)
        att_type = ActivityAttachmentType(
            activity_id=activity.id, name="PDF Only",
            allowed_extensions=["pdf"], max_file_size_mb=5,
            is_mandatory=True, is_active=True,
        )
        db.add(att_type)
        db.flush()

        reg = Registration(
            activity_id=activity.id, member_id=member.id,
            price_id=price.id, status="confirmed",
        )
        db.add(reg)
        db.flush()

        client.cookies.update(_auth_cookie(user))
        response = client.post(
            f"/api/v1/registrations/{reg.id}/attachments?attachment_type_id={att_type.id}",
            files={"file": ("photo.jpg", io.BytesIO(b"fake image"), "image/jpeg")},
        )
        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"].lower()

    def test_upload_exceeds_size_limit(self, client, db):
        admin = _create_user(db, "admin", suffix="-fu3")
        user, member = _create_member_with_user(db, suffix="-fu3")
        activity, price = _create_published_activity(db, admin.id)
        att_type = ActivityAttachmentType(
            activity_id=activity.id, name="Tiny Limit",
            allowed_extensions=["txt"], max_file_size_mb=1,
            is_mandatory=False, is_active=True,
        )
        db.add(att_type)
        db.flush()

        reg = Registration(
            activity_id=activity.id, member_id=member.id,
            price_id=price.id, status="confirmed",
        )
        db.add(reg)
        db.flush()

        # Create a file larger than 1MB
        large_content = b"x" * (1 * 1024 * 1024 + 1)
        client.cookies.update(_auth_cookie(user))
        response = client.post(
            f"/api/v1/registrations/{reg.id}/attachments?attachment_type_id={att_type.id}",
            files={"file": ("big.txt", io.BytesIO(large_content), "text/plain")},
        )
        assert response.status_code == 400
        assert "maximum size" in response.json()["detail"].lower()

    def test_list_registration_attachments(self, client, db):
        admin = _create_user(db, "admin", suffix="-fu4")
        user, member = _create_member_with_user(db, suffix="-fu4")
        activity, price = _create_published_activity(db, admin.id)

        reg = Registration(
            activity_id=activity.id, member_id=member.id,
            price_id=price.id, status="confirmed",
        )
        db.add(reg)
        db.flush()

        # Upload a file first
        client.cookies.update(_auth_cookie(user))
        client.post(
            f"/api/v1/registrations/{reg.id}/attachments",
            files={"file": ("doc.txt", io.BytesIO(b"content"), "text/plain")},
        )

        # List attachments
        response = client.get(f"/api/v1/registrations/{reg.id}/attachments")
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_other_member_cannot_upload(self, client, db):
        admin = _create_user(db, "admin", suffix="-fu5")
        _, member1 = _create_member_with_user(db, suffix="-fu5a")
        user2, _ = _create_member_with_user(db, suffix="-fu5b")
        activity, price = _create_published_activity(db, admin.id)

        reg = Registration(
            activity_id=activity.id, member_id=member1.id,
            price_id=price.id, status="confirmed",
        )
        db.add(reg)
        db.flush()

        # Try to upload as different member
        client.cookies.update(_auth_cookie(user2))
        response = client.post(
            f"/api/v1/registrations/{reg.id}/attachments",
            files={"file": ("sneaky.txt", io.BytesIO(b"nope"), "text/plain")},
        )
        assert response.status_code == 403

    def test_admin_can_view_attachments(self, client, db):
        admin = _create_user(db, "admin", suffix="-fu6")
        user, member = _create_member_with_user(db, suffix="-fu6")
        activity, price = _create_published_activity(db, admin.id)

        reg = Registration(
            activity_id=activity.id, member_id=member.id,
            price_id=price.id, status="confirmed",
        )
        db.add(reg)
        db.flush()

        # Upload as member
        client.cookies.update(_auth_cookie(user))
        client.post(
            f"/api/v1/registrations/{reg.id}/attachments",
            files={"file": ("cert.txt", io.BytesIO(b"certificate"), "text/plain")},
        )

        # Admin can view
        client.cookies.update(_auth_cookie(admin))
        response = client.get(f"/api/v1/registrations/{reg.id}/attachments")
        assert response.status_code == 200
        assert len(response.json()) >= 1
