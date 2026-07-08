"""Integration tests for the admin notes & reminders endpoints."""

from datetime import date, datetime, timezone

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.members.models import Member
from app.domains.persons.models import Person
from app.domains.reminders.models import Reminder


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id, user.role)}


def _admin(db, suffix):
    person = Person(first_name="Admin", last_name="User", email=f"admin-rem-{suffix}@test.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=f"admin-rem-{suffix}@test.com",
        password_hash=hash_password("password123"),
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _member_user(db, suffix):
    person = Person(first_name="Mem", last_name=f"Ber-{suffix}", email=f"m-rem-{suffix}@test.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=f"m-rem-{suffix}@test.com",
        password_hash=hash_password("password123"),
        role="member",
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(Member(person_id=person.id, user_id=user.id, member_number=f"M-rem-{suffix}", status="active"))
    db.flush()
    return user


class TestReminderCreate:
    def test_create_note_has_no_due_date(self, client, db):
        admin = _admin(db, "note")
        client.cookies.update(_auth_cookie(admin))

        resp = client.post("/api/v1/reminders", json={"content": "Call the auditor"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["content"] == "Call the auditor"
        assert body["due_date"] is None
        assert body["is_done"] is False
        assert body["created_by"] == admin.id

    def test_create_dated_reminder(self, client, db):
        admin = _admin(db, "dated")
        client.cookies.update(_auth_cookie(admin))

        resp = client.post(
            "/api/v1/reminders",
            json={"content": "Send fees", "due_date": "2026-09-01"},
        )
        assert resp.status_code == 201
        assert resp.json()["due_date"] == "2026-09-01"

    def test_blank_content_rejected(self, client, db):
        admin = _admin(db, "blank")
        client.cookies.update(_auth_cookie(admin))

        resp = client.post("/api/v1/reminders", json={"content": ""})
        assert resp.status_code == 422


class TestReminderList:
    def test_ordering_open_first_then_due_nulls_last(self, client, db):
        admin = _admin(db, "order")
        # Two done, three open with mixed due dates; created_at controls the note tie-break.
        db.add_all([
            Reminder(content="done-item", is_done=True, created_by=admin.id),
            Reminder(content="due-late", due_date=date(2026, 12, 1), created_by=admin.id,
                     created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
            Reminder(content="due-early", due_date=date(2026, 3, 1), created_by=admin.id,
                     created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)),
            Reminder(content="note-newer", created_by=admin.id,
                     created_at=datetime(2026, 2, 1, tzinfo=timezone.utc)),
        ])
        db.flush()
        client.cookies.update(_auth_cookie(admin))

        resp = client.get("/api/v1/reminders")
        assert resp.status_code == 200
        names = [r["content"] for r in resp.json()]
        # Open first (due asc, nulls last), done last.
        assert names == ["due-early", "due-late", "note-newer", "done-item"]

    def test_only_open_hides_done(self, client, db):
        admin = _admin(db, "open")
        db.add_all([
            Reminder(content="still-open", created_by=admin.id),
            Reminder(content="finished", is_done=True, created_by=admin.id),
        ])
        db.flush()
        client.cookies.update(_auth_cookie(admin))

        resp = client.get("/api/v1/reminders?only_open=true")
        contents = [r["content"] for r in resp.json()]
        assert contents == ["still-open"]


class TestReminderUpdate:
    def test_toggle_done(self, client, db):
        admin = _admin(db, "toggle")
        reminder = Reminder(content="tick me", created_by=admin.id)
        db.add(reminder)
        db.flush()
        client.cookies.update(_auth_cookie(admin))

        resp = client.patch(f"/api/v1/reminders/{reminder.id}", json={"is_done": True})
        assert resp.status_code == 200
        assert resp.json()["is_done"] is True

    def test_clear_due_date_turns_reminder_into_note(self, client, db):
        admin = _admin(db, "clear")
        reminder = Reminder(content="was dated", due_date=date(2026, 5, 1), created_by=admin.id)
        db.add(reminder)
        db.flush()
        client.cookies.update(_auth_cookie(admin))

        resp = client.patch(f"/api/v1/reminders/{reminder.id}", json={"due_date": None})
        assert resp.status_code == 200
        assert resp.json()["due_date"] is None

    def test_content_omitted_is_untouched(self, client, db):
        admin = _admin(db, "omit")
        reminder = Reminder(content="keep this text", created_by=admin.id)
        db.add(reminder)
        db.flush()
        client.cookies.update(_auth_cookie(admin))

        resp = client.patch(f"/api/v1/reminders/{reminder.id}", json={"is_done": True})
        assert resp.json()["content"] == "keep this text"

    def test_update_missing_is_404(self, client, db):
        admin = _admin(db, "missing")
        client.cookies.update(_auth_cookie(admin))

        resp = client.patch("/api/v1/reminders/999999", json={"is_done": True})
        assert resp.status_code == 404


class TestReminderDelete:
    def test_delete_returns_204(self, client, db):
        admin = _admin(db, "del")
        reminder = Reminder(content="delete me", created_by=admin.id)
        db.add(reminder)
        db.flush()
        rid = reminder.id
        client.cookies.update(_auth_cookie(admin))

        resp = client.delete(f"/api/v1/reminders/{rid}")
        assert resp.status_code == 204
        assert db.get(Reminder, rid) is None

    def test_delete_missing_is_404(self, client, db):
        admin = _admin(db, "del-missing")
        client.cookies.update(_auth_cookie(admin))

        resp = client.delete("/api/v1/reminders/999999")
        assert resp.status_code == 404


class TestReminderAuth:
    def test_non_admin_forbidden(self, client, db):
        user = _member_user(db, "forbidden")
        client.cookies.update(_auth_cookie(user))

        assert client.get("/api/v1/reminders").status_code == 403
        assert client.post("/api/v1/reminders", json={"content": "x"}).status_code == 403
