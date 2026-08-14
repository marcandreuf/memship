"""Integration tests for v0.5.0 Simple Communications.

Covers the audience resolver, the draft→send workflow (snapshot, notification
fan-out, immutability), RBAC, and the member notification surface.
"""

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.communications import service
from app.domains.communications.models import (
    Announcement,
    AnnouncementRecipient,
    Notification,
)
from app.domains.members.models import Group, Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id)}


def _create_user(db, role="admin", suffix="u"):
    person = Person(first_name="Test", last_name="User", email=f"{suffix}-{role}@examplee6e3b1.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=person.email,
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _ensure_org(db, features=None):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(
            id=1,
            name="Test Organization",
            locale="es",
            timezone="Europe/Madrid",
            currency="EUR",
            date_format="DD/MM/YYYY",
            invoice_prefix="FAC",
            invoice_next_number=1,
            invoice_annual_reset=True,
            default_vat_rate=21.00,
        )
        db.add(org)
        db.flush()
    if features is not None:
        org.features = features
        db.flush()
    return org


def _group(db, suffix):
    g = Group(name=f"Group {suffix}", slug=f"group-{suffix}")
    db.add(g)
    db.flush()
    return g


def _mtype(db, suffix, group_id=None):
    mt = MembershipType(
        name=f"Type {suffix}",
        slug=f"type-{suffix}",
        base_price=10,
        billing_frequency="annual",
        group_id=group_id,
    )
    db.add(mt)
    db.flush()
    return mt


def _create_member(
    db,
    suffix,
    status="active",
    is_active=True,
    with_user=False,
    opted_out=False,
    mtype=None,
):
    person = Person(first_name="Mem", last_name=suffix, email=f"mem-{suffix}@examplee6e3b1.com")
    db.add(person)
    db.flush()
    user_id = None
    if with_user:
        u = User(
            person_id=person.id,
            email=person.email,
            password_hash=hash_password("password123"),
            role="member",
            is_active=True,
        )
        db.add(u)
        db.flush()
        user_id = u.id
    if mtype is None:
        mtype = _mtype(db, suffix)
    member = Member(
        person_id=person.id,
        user_id=user_id,
        membership_type_id=mtype.id,
        member_number=f"M-{suffix}",
        status=status,
        is_active=is_active,
        communication_preferences={"email": not opted_out, "sms": False, "push": False},
    )
    db.add(member)
    db.flush()
    return member


def _draft(db, admin, target_type="all", target_id=None, subject="Hello", body="Body"):
    ann = Announcement(
        subject=subject,
        body=body,
        target_type=target_type,
        target_id=target_id,
        status="draft",
        created_by_user_id=admin.id,
    )
    db.add(ann)
    db.flush()
    return ann


# --- Audience resolver (service level) ---


class TestAudienceResolver:
    def test_all_active_only(self, db):
        _create_member(db, "aa-active", status="active")
        _create_member(db, "aa-pending", status="pending")
        _create_member(db, "aa-inactive", status="active", is_active=False)
        members = service.resolve_audience(db, "all", None)
        assert {m.member_number for m in members} == {"M-aa-active"}

    def test_group_target(self, db):
        g = _group(db, "rg")
        mt_in = _mtype(db, "rg-in", group_id=g.id)
        mt_out = _mtype(db, "rg-out")
        _create_member(db, "rg1", mtype=mt_in)
        _create_member(db, "rg2", mtype=mt_in)
        _create_member(db, "rg3", mtype=mt_out)
        members = service.resolve_audience(db, "group", g.id)
        assert {m.member_number for m in members} == {"M-rg1", "M-rg2"}

    def test_membership_type_target(self, db):
        mt = _mtype(db, "rmt")
        _create_member(db, "rmt1", mtype=mt)
        _create_member(db, "rmt2")  # different (auto) membership type
        members = service.resolve_audience(db, "membership_type", mt.id)
        assert {m.member_number for m in members} == {"M-rmt1"}

    def test_email_recipients_skips_opt_out(self, db):
        _create_member(db, "eo-in")
        _create_member(db, "eo-out", opted_out=True)
        members = service.resolve_audience(db, "all", None)
        emails = {p.email for p in service.email_recipients(db, members)}
        assert emails == {"mem-eo-in@examplee6e3b1.com"}
        # Opted-out member is still part of the resolved audience (gets in-app).
        assert len(members) == 2


# --- Draft → send workflow (endpoint level) ---


class TestDraftSend:
    def test_create_draft(self, client, db):
        admin = _create_user(db, "admin", "cd")
        _ensure_org(db)
        resp = client.post(
            "/api/v1/announcements",
            json={"subject": "Hi", "body": "Body", "target_type": "all"},
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "draft"
        assert body["target_type"] == "all"
        assert body["recipient_count"] is None

    def test_create_all_with_target_id_422(self, client, db):
        admin = _create_user(db, "admin", "ct")
        _ensure_org(db)
        resp = client.post(
            "/api/v1/announcements",
            json={"subject": "Hi", "body": "B", "target_type": "all", "target_id": 5},
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 422

    def test_create_group_without_target_id_422(self, client, db):
        admin = _create_user(db, "admin", "cg")
        _ensure_org(db)
        resp = client.post(
            "/api/v1/announcements",
            json={"subject": "Hi", "body": "B", "target_type": "group"},
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 422

    def test_update_draft(self, client, db):
        admin = _create_user(db, "admin", "ud")
        _ensure_org(db)
        ann = _draft(db, admin)
        resp = client.put(
            f"/api/v1/announcements/{ann.id}",
            json={"subject": "Edited"},
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["subject"] == "Edited"

    def test_send_flips_and_snapshots_and_notifies(self, client, db):
        admin = _create_user(db, "admin", "sf")
        _ensure_org(db)
        m = _create_member(db, "sf1", with_user=True)
        ann = _draft(db, admin, target_type="all")

        resp = client.post(
            f"/api/v1/announcements/{ann.id}/send", cookies=_auth_cookie(admin)
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "sent"
        assert body["recipient_count"] == 1
        assert body["sent_at"] is not None

        notes = (
            db.query(Notification).filter(Notification.user_id == m.user_id).all()
        )
        assert len(notes) == 1
        assert notes[0].source_type == "announcement"
        assert notes[0].source_id == ann.id

    def test_send_no_user_account_no_notification(self, client, db):
        admin = _create_user(db, "admin", "snu")
        _ensure_org(db)
        _create_member(db, "snu1", with_user=False)
        ann = _draft(db, admin, target_type="all")
        resp = client.post(
            f"/api/v1/announcements/{ann.id}/send", cookies=_auth_cookie(admin)
        )
        assert resp.status_code == 200
        assert resp.json()["recipient_count"] == 1
        assert db.query(Notification).count() == 0

    def test_send_again_409(self, client, db):
        admin = _create_user(db, "admin", "sa")
        _ensure_org(db)
        _create_member(db, "sa1", with_user=True)
        ann = _draft(db, admin, target_type="all")
        first = client.post(
            f"/api/v1/announcements/{ann.id}/send", cookies=_auth_cookie(admin)
        )
        assert first.status_code == 200
        again = client.post(
            f"/api/v1/announcements/{ann.id}/send", cookies=_auth_cookie(admin)
        )
        assert again.status_code == 409

    def test_send_empty_audience_409(self, client, db):
        admin = _create_user(db, "admin", "se")
        _ensure_org(db)
        ann = _draft(db, admin, target_type="all")  # no members exist
        resp = client.post(
            f"/api/v1/announcements/{ann.id}/send", cookies=_auth_cookie(admin)
        )
        assert resp.status_code == 409

    def test_update_sent_is_409(self, client, db):
        admin = _create_user(db, "admin", "us")
        _ensure_org(db)
        _create_member(db, "us1", with_user=True)
        ann = _draft(db, admin, target_type="all")
        client.post(f"/api/v1/announcements/{ann.id}/send", cookies=_auth_cookie(admin))
        resp = client.put(
            f"/api/v1/announcements/{ann.id}",
            json={"subject": "Nope"},
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 409

    def test_send_404(self, client, db):
        admin = _create_user(db, "admin", "s404")
        _ensure_org(db)
        resp = client.post(
            "/api/v1/announcements/999999/send", cookies=_auth_cookie(admin)
        )
        assert resp.status_code == 404

    def test_audience_preview_count(self, client, db):
        admin = _create_user(db, "admin", "ap")
        _ensure_org(db)
        _create_member(db, "ap1")
        _create_member(db, "ap2")
        ann = _draft(db, admin, target_type="all")
        resp = client.get(
            f"/api/v1/announcements/{ann.id}/audience-preview",
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 2


# --- RBAC ---


class TestRBAC:
    def test_create_forbidden_for_member(self, client, db):
        member_user = _create_user(db, "member", "rbc")
        _ensure_org(db)
        resp = client.post(
            "/api/v1/announcements",
            json={"subject": "Hi", "body": "B", "target_type": "all"},
            cookies=_auth_cookie(member_user),
        )
        assert resp.status_code == 403

    def test_send_forbidden_for_member(self, client, db):
        admin = _create_user(db, "admin", "rbs-a")
        member_user = _create_user(db, "member", "rbs-m")
        _ensure_org(db)
        ann = _draft(db, admin, target_type="all")
        resp = client.post(
            f"/api/v1/announcements/{ann.id}/send",
            cookies=_auth_cookie(member_user),
        )
        assert resp.status_code == 403

    def test_member_sees_only_own_notifications(self, client, db):
        admin = _create_user(db, "admin", "own-a")
        u1 = _create_user(db, "member", "own1")
        u2 = _create_user(db, "member", "own2")
        _ensure_org(db)
        db.add(Notification(user_id=u1.id, source_type="announcement", source_id=1, title="A"))
        db.add(Notification(user_id=u2.id, source_type="announcement", source_id=1, title="B"))
        db.flush()

        resp = client.get("/api/v1/me/notifications", cookies=_auth_cookie(u1))
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["title"] == "A"


# --- Notification surface ---


class TestNotifications:
    def test_unread_count(self, client, db):
        u = _create_user(db, "member", "uc")
        _ensure_org(db)
        db.add(Notification(user_id=u.id, source_type="announcement", source_id=1, title="A"))
        db.add(Notification(user_id=u.id, source_type="announcement", source_id=2, title="B"))
        db.flush()
        resp = client.get(
            "/api/v1/me/notifications/unread-count", cookies=_auth_cookie(u)
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 2

    def test_mark_read_by_ids(self, client, db):
        u = _create_user(db, "member", "mri")
        _ensure_org(db)
        n1 = Notification(user_id=u.id, source_type="announcement", source_id=1, title="A")
        n2 = Notification(user_id=u.id, source_type="announcement", source_id=2, title="B")
        db.add_all([n1, n2])
        db.flush()

        resp = client.post(
            "/api/v1/me/notifications/mark-read",
            json={"ids": [n1.id]},
            cookies=_auth_cookie(u),
        )
        assert resp.status_code == 200
        assert resp.json()["updated"] == 1
        assert service.unread_count(db, u) == 1

    def test_mark_read_all(self, client, db):
        u = _create_user(db, "member", "mra")
        _ensure_org(db)
        db.add(Notification(user_id=u.id, source_type="announcement", source_id=1, title="A"))
        db.add(Notification(user_id=u.id, source_type="announcement", source_id=2, title="B"))
        db.flush()
        resp = client.post(
            "/api/v1/me/notifications/mark-read",
            json={"all": True},
            cookies=_auth_cookie(u),
        )
        assert resp.status_code == 200
        assert resp.json()["updated"] == 2
        assert service.unread_count(db, u) == 0

    def test_mark_read_does_not_touch_others(self, client, db):
        u1 = _create_user(db, "member", "mro1")
        u2 = _create_user(db, "member", "mro2")
        _ensure_org(db)
        other = Notification(user_id=u2.id, source_type="announcement", source_id=1, title="B")
        db.add(other)
        db.flush()
        client.post(
            "/api/v1/me/notifications/mark-read",
            json={"all": True},
            cookies=_auth_cookie(u1),
        )
        assert service.unread_count(db, u2) == 1

    def test_member_announcements_received(self, client, db):
        admin = _create_user(db, "admin", "mar-a")
        _ensure_org(db)
        member = _create_member(db, "mar1", with_user=True)
        ann = _draft(db, admin, target_type="all", subject="News")
        client.post(f"/api/v1/announcements/{ann.id}/send", cookies=_auth_cookie(admin))

        member_user = db.query(User).filter(User.id == member.user_id).first()
        resp = client.get(
            "/api/v1/me/announcements", cookies=_auth_cookie(member_user)
        )
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["subject"] == "News"


# --- Recipient snapshot + sent view (v0.5.1) ---


class TestRecipients:
    def test_send_creates_recipient_snapshot(self, client, db):
        admin = _create_user(db, "admin", "rs-a")
        _ensure_org(db)
        with_acct = _create_member(db, "rs-acct", with_user=True)
        email_only = _create_member(db, "rs-email", with_user=False)
        opted_out = _create_member(db, "rs-optout", with_user=True, opted_out=True)
        ann = _draft(db, admin, target_type="all")
        client.post(f"/api/v1/announcements/{ann.id}/send", cookies=_auth_cookie(admin))

        recips = {
            r.member_id: r
            for r in db.query(AnnouncementRecipient).filter(
                AnnouncementRecipient.announcement_id == ann.id
            )
        }
        assert set(recips) == {with_acct.id, email_only.id, opted_out.id}
        # Member with account: emailed + in-app.
        assert recips[with_acct.id].emailed is True
        assert recips[with_acct.id].in_app is True
        # Email-only member: emailed, not in-app, no user_id.
        assert recips[email_only.id].emailed is True
        assert recips[email_only.id].in_app is False
        assert recips[email_only.id].user_id is None
        # Opted-out member: not emailed, but still in-app (has account).
        assert recips[opted_out.id].emailed is False
        assert recips[opted_out.id].in_app is True

    def test_recipients_endpoint_lists_and_paginates(self, client, db):
        admin = _create_user(db, "admin", "rl-a")
        _ensure_org(db)
        for i in range(3):
            _create_member(db, f"rl{i}", with_user=(i % 2 == 0))
        ann = _draft(db, admin, target_type="all")
        client.post(f"/api/v1/announcements/{ann.id}/send", cookies=_auth_cookie(admin))

        resp = client.get(
            f"/api/v1/announcements/{ann.id}/recipients?page=1&per_page=2",
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 3
        assert body["meta"]["total_pages"] == 2
        assert len(body["items"]) == 2
        item = body["items"][0]
        assert {"member_id", "name", "email", "emailed", "in_app", "seen_at"} <= item.keys()
        # Not yet opened by anyone.
        assert all(i["seen_at"] is None for i in body["items"])

    def test_recipient_seen_reflects_read_at(self, client, db):
        admin = _create_user(db, "admin", "rsn-a")
        _ensure_org(db)
        member = _create_member(db, "rsn1", with_user=True)
        ann = _draft(db, admin, target_type="all")
        client.post(f"/api/v1/announcements/{ann.id}/send", cookies=_auth_cookie(admin))

        # Member opens it — marks the notification read.
        member_user = db.query(User).filter(User.id == member.user_id).first()
        client.post(
            "/api/v1/me/notifications/mark-read",
            json={"all": True},
            cookies=_auth_cookie(member_user),
        )

        resp = client.get(
            f"/api/v1/announcements/{ann.id}/recipients",
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert item["member_id"] == member.id
        assert item["seen_at"] is not None

    def test_email_only_recipient_never_seen(self, client, db):
        admin = _create_user(db, "admin", "reo-a")
        _ensure_org(db)
        _create_member(db, "reo1", with_user=False)
        ann = _draft(db, admin, target_type="all")
        client.post(f"/api/v1/announcements/{ann.id}/send", cookies=_auth_cookie(admin))

        resp = client.get(
            f"/api/v1/announcements/{ann.id}/recipients",
            cookies=_auth_cookie(admin),
        )
        item = resp.json()["items"][0]
        assert item["in_app"] is False
        assert item["seen_at"] is None

    def test_stats_counts(self, client, db):
        admin = _create_user(db, "admin", "st-a")
        _ensure_org(db)
        seen_member = _create_member(db, "st-seen", with_user=True)
        _create_member(db, "st-unseen", with_user=True)
        _create_member(db, "st-email", with_user=False)
        _create_member(db, "st-optout", with_user=True, opted_out=True)
        ann = _draft(db, admin, target_type="all")
        client.post(f"/api/v1/announcements/{ann.id}/send", cookies=_auth_cookie(admin))

        seen_user = db.query(User).filter(User.id == seen_member.user_id).first()
        client.post(
            "/api/v1/me/notifications/mark-read",
            json={"all": True},
            cookies=_auth_cookie(seen_user),
        )

        resp = client.get(
            f"/api/v1/announcements/{ann.id}/stats", cookies=_auth_cookie(admin)
        )
        assert resp.status_code == 200
        stats = resp.json()
        assert stats["recipient_count"] == 4
        assert stats["emailed_count"] == 3  # all but the opted-out member
        assert stats["seen_count"] == 1
        assert stats["sent_by"] == "Test User"  # from _create_user

    def test_recipients_forbidden_for_member(self, client, db):
        admin = _create_user(db, "admin", "rf-a")
        member_user = _create_user(db, "member", "rf-m")
        _ensure_org(db)
        _create_member(db, "rf1", with_user=True)
        ann = _draft(db, admin, target_type="all")
        client.post(f"/api/v1/announcements/{ann.id}/send", cookies=_auth_cookie(admin))
        resp = client.get(
            f"/api/v1/announcements/{ann.id}/recipients",
            cookies=_auth_cookie(member_user),
        )
        assert resp.status_code == 403

    def test_recipients_404_for_missing(self, client, db):
        admin = _create_user(db, "admin", "r404")
        _ensure_org(db)
        resp = client.get(
            "/api/v1/announcements/999999/recipients", cookies=_auth_cookie(admin)
        )
        assert resp.status_code == 404
