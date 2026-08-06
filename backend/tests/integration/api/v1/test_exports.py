"""Integration tests for the admin CSV export endpoints.

Each export mirrors the filters of its sibling list endpoint (shared query
builder), streams ``text/csv`` with a UTF-8 BOM, and is admin-only.
"""

import csv
import io
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.activities.models import Activity, ActivityModality, Registration
from app.domains.auth.models import User
from app.domains.billing.models import Concept, Receipt
from app.domains.members.models import Group, Member, MembershipType
from app.domains.persons.models import Person


# --- Helpers ---


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id)}


def _admin(db, suffix="exp"):
    person = Person(first_name="Admin", last_name="User", email=f"admin-{suffix}@test.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=f"admin-{suffix}@test.com",
        password_hash=hash_password("password123"),
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _member(db, suffix, *, status="active", membership_type=None, with_user=False):
    person = Person(
        first_name="María", last_name=f"García-{suffix}", email=f"m-{suffix}@test.com"
    )
    db.add(person)
    db.flush()
    user_id = None
    role_user = None
    if with_user:
        role_user = User(
            person_id=person.id,
            email=f"m-{suffix}@test.com",
            password_hash=hash_password("password123"),
            role="member",
            is_active=True,
        )
        db.add(role_user)
        db.flush()
        user_id = role_user.id
    member = Member(
        person_id=person.id,
        user_id=user_id,
        membership_type_id=membership_type.id if membership_type else None,
        member_number=f"M-{suffix}",
        status=status,
    )
    db.add(member)
    db.flush()
    return (member, role_user) if with_user else member


def _membership_type(db, suffix, group=None):
    mt = MembershipType(
        name=f"Full {suffix}",
        slug=f"full-{suffix}",
        group_id=group.id if group else None,
        is_active=True,
    )
    db.add(mt)
    db.flush()
    return mt


def _concept(db, suffix):
    concept = Concept(
        name=f"Membership Fee {suffix}",
        code=f"fee-{suffix}",
        concept_type="membership",
        default_amount=Decimal("100.00"),
        vat_rate=Decimal("21.00"),
    )
    db.add(concept)
    db.flush()
    return concept


def _receipt(db, member, *, suffix, emission_date, status="emitted", concept=None):
    receipt = Receipt(
        receipt_number=f"FAC-{suffix}",
        member_id=member.id,
        concept_id=concept.id if concept else None,
        origin="membership",
        description=f"Receipt {suffix}",
        base_amount=Decimal("100.00"),
        vat_rate=Decimal("21.00"),
        vat_amount=Decimal("21.00"),
        total_amount=Decimal("121.00"),
        status=status,
        emission_date=emission_date,
    )
    db.add(receipt)
    db.flush()
    return receipt


def _activity(db, suffix):
    now = datetime.now(timezone.utc)
    activity = Activity(
        name=f"Yoga {suffix}",
        slug=f"yoga-{suffix}",
        starts_at=now + timedelta(days=10),
        ends_at=now + timedelta(days=11),
        registration_starts_at=now - timedelta(days=1),
        registration_ends_at=now + timedelta(days=9),
        max_participants=50,
        status="published",
        is_active=True,
    )
    db.add(activity)
    db.flush()
    return activity


def _modality(db, activity, name="Standard"):
    modality = ActivityModality(activity_id=activity.id, name=name)
    db.add(modality)
    db.flush()
    return modality


def _registration(db, activity, member, *, status="confirmed", modality=None):
    reg = Registration(
        activity_id=activity.id,
        member_id=member.id,
        modality_id=modality.id if modality else None,
        status=status,
        original_amount=Decimal("30.00"),
        discounted_amount=Decimal("25.00"),
    )
    db.add(reg)
    db.flush()
    return reg


def _parse_csv(response):
    """Return (headers, data_rows) from a CSV response, stripping the BOM."""
    text = response.text
    if text.startswith("﻿"):
        text = text[1:]
    rows = list(csv.reader(io.StringIO(text)))
    return rows[0], rows[1:]


# --- Members export ---


class TestMembersExport:
    def test_content_type_and_headers(self, client, db):
        admin = _admin(db, "m-ct")
        _member(db, "m-ct-1")
        client.cookies.update(_auth_cookie(admin))

        resp = client.get("/api/v1/members/export.csv")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert 'attachment; filename="members.csv"' in resp.headers["content-disposition"]
        # BOM present for Excel
        assert resp.text.startswith("﻿")

        headers, rows = _parse_csv(resp)
        assert headers == [
            "id", "member_number", "first_name", "last_name", "email",
            "status", "membership_type", "group", "joined_at", "expires_at", "is_minor",
        ]
        assert len(rows) == 1
        assert rows[0][1] == "M-m-ct-1"

    def test_empty_returns_header_only(self, client, db):
        admin = _admin(db, "m-empty")
        client.cookies.update(_auth_cookie(admin))

        resp = client.get("/api/v1/members/export.csv")
        assert resp.status_code == 200
        headers, rows = _parse_csv(resp)
        assert headers[0] == "id"
        assert rows == []

    def test_respects_status_filter(self, client, db):
        admin = _admin(db, "m-status")
        _member(db, "m-active", status="active")
        _member(db, "m-cancelled", status="cancelled")
        client.cookies.update(_auth_cookie(admin))

        resp = client.get("/api/v1/members/export.csv?status=active")
        _, rows = _parse_csv(resp)
        numbers = {r[1] for r in rows}
        assert "M-m-active" in numbers
        assert "M-m-cancelled" not in numbers

    def test_respects_search_filter(self, client, db):
        admin = _admin(db, "m-search")
        _member(db, "findme")
        _member(db, "other")
        client.cookies.update(_auth_cookie(admin))

        resp = client.get("/api/v1/members/export.csv?search=findme")
        _, rows = _parse_csv(resp)
        assert len(rows) == 1
        assert rows[0][1] == "M-findme"

    def test_membership_type_and_group_columns(self, client, db):
        admin = _admin(db, "m-grp")
        group = Group(name="Youth", slug="youth-exp", is_active=True)
        db.add(group)
        db.flush()
        mt = _membership_type(db, "grp", group=group)
        _member(db, "m-grp-1", membership_type=mt)
        client.cookies.update(_auth_cookie(admin))

        resp = client.get("/api/v1/members/export.csv")
        headers, rows = _parse_csv(resp)
        row = rows[0]
        assert row[headers.index("membership_type")] == "Full grp"
        assert row[headers.index("group")] == "Youth"

    def test_non_admin_forbidden(self, client, db):
        member, user = _member(db, "m-forbidden", with_user=True)
        client.cookies.update(_auth_cookie(user))

        resp = client.get("/api/v1/members/export.csv")
        assert resp.status_code == 403


# --- Receipts export ---


class TestReceiptsExport:
    def test_columns_populated(self, client, db):
        admin = _admin(db, "r-cols")
        member = _member(db, "r-cols-m")
        concept = _concept(db, "r-cols")
        _receipt(db, member, suffix="r-cols-1", emission_date=date(2026, 3, 15), concept=concept)
        client.cookies.update(_auth_cookie(admin))

        resp = client.get("/api/v1/receipts/export.csv")
        assert resp.status_code == 200
        assert 'filename="receipts.csv"' in resp.headers["content-disposition"]
        headers, rows = _parse_csv(resp)
        assert headers == [
            "receipt_number", "member_number", "member_name", "concept", "origin",
            "status", "base_amount", "vat_amount", "total_amount",
            "emission_date", "due_date", "payment_date",
        ]
        assert len(rows) == 1
        row = rows[0]
        assert row[headers.index("receipt_number")] == "FAC-r-cols-1"
        assert row[headers.index("member_number")] == "M-r-cols-m"
        assert row[headers.index("member_name")] == "María García-r-cols-m"
        assert row[headers.index("concept")] == "Membership Fee r-cols"
        assert row[headers.index("total_amount")] == "121.00"

    def test_date_range_filter(self, client, db):
        admin = _admin(db, "r-date")
        member = _member(db, "r-date-m")
        _receipt(db, member, suffix="r-jan", emission_date=date(2026, 1, 10))
        _receipt(db, member, suffix="r-jun", emission_date=date(2026, 6, 10))
        _receipt(db, member, suffix="r-dec", emission_date=date(2026, 12, 10))
        client.cookies.update(_auth_cookie(admin))

        resp = client.get(
            "/api/v1/receipts/export.csv"
            "?emission_date_from=2026-03-01&emission_date_to=2026-09-01"
        )
        _, rows = _parse_csv(resp)
        numbers = {r[0] for r in rows}
        assert numbers == {"FAC-r-jun"}

    def test_status_filter(self, client, db):
        admin = _admin(db, "r-status")
        member = _member(db, "r-status-m")
        _receipt(db, member, suffix="r-paid", emission_date=date(2026, 2, 1), status="paid")
        _receipt(db, member, suffix="r-emitted", emission_date=date(2026, 2, 2), status="emitted")
        client.cookies.update(_auth_cookie(admin))

        resp = client.get("/api/v1/receipts/export.csv?status=paid")
        _, rows = _parse_csv(resp)
        numbers = {r[0] for r in rows}
        assert numbers == {"FAC-r-paid"}

    def test_non_admin_forbidden(self, client, db):
        member, user = _member(db, "r-forbidden", with_user=True)
        client.cookies.update(_auth_cookie(user))

        resp = client.get("/api/v1/receipts/export.csv")
        assert resp.status_code == 403


# --- Registrations export ---


class TestRegistrationsExport:
    def test_activity_registrations_export(self, client, db):
        admin = _admin(db, "reg-act")
        activity = _activity(db, "reg-act")
        modality = _modality(db, activity, name="Morning")
        member = _member(db, "reg-act-m")
        _registration(db, activity, member, status="confirmed", modality=modality)
        client.cookies.update(_auth_cookie(admin))

        resp = client.get(f"/api/v1/activities/{activity.id}/registrations/export.csv")
        assert resp.status_code == 200
        assert f'filename="activity-{activity.id}-registrations.csv"' in resp.headers["content-disposition"]
        headers, rows = _parse_csv(resp)
        assert headers == [
            "activity_name", "member_number", "member_name", "modality", "status",
            "original_amount", "discounted_amount", "created_at", "cancelled_at",
        ]
        assert len(rows) == 1
        row = rows[0]
        assert row[headers.index("activity_name")] == "Yoga reg-act"
        assert row[headers.index("member_number")] == "M-reg-act-m"
        assert row[headers.index("modality")] == "Morning"
        assert row[headers.index("status")] == "confirmed"

    def test_activity_registrations_status_filter(self, client, db):
        admin = _admin(db, "reg-filter")
        activity = _activity(db, "reg-filter")
        m1 = _member(db, "reg-conf")
        m2 = _member(db, "reg-wait")
        _registration(db, activity, m1, status="confirmed")
        _registration(db, activity, m2, status="waitlist")
        client.cookies.update(_auth_cookie(admin))

        resp = client.get(
            f"/api/v1/activities/{activity.id}/registrations/export.csv?status=confirmed"
        )
        headers, rows = _parse_csv(resp)
        statuses = {r[headers.index("status")] for r in rows}
        numbers = {r[headers.index("member_number")] for r in rows}
        assert statuses == {"confirmed"}
        assert numbers == {"M-reg-conf"}

    def test_member_registrations_export(self, client, db):
        admin = _admin(db, "reg-mem")
        activity = _activity(db, "reg-mem")
        member = _member(db, "reg-mem-m")
        _registration(db, activity, member, status="confirmed")
        client.cookies.update(_auth_cookie(admin))

        resp = client.get(f"/api/v1/members/{member.id}/registrations/export.csv")
        assert resp.status_code == 200
        assert f'filename="member-{member.id}-registrations.csv"' in resp.headers["content-disposition"]
        headers, rows = _parse_csv(resp)
        assert len(rows) == 1
        assert rows[0][headers.index("activity_name")] == "Yoga reg-mem"

    def test_member_registrations_unknown_member_404(self, client, db):
        admin = _admin(db, "reg-404")
        client.cookies.update(_auth_cookie(admin))

        resp = client.get("/api/v1/members/999999/registrations/export.csv")
        assert resp.status_code == 404

    def test_non_admin_forbidden(self, client, db):
        member, user = _member(db, "reg-forbidden", with_user=True)
        activity = _activity(db, "reg-forbidden")
        client.cookies.update(_auth_cookie(user))

        resp = client.get(f"/api/v1/activities/{activity.id}/registrations/export.csv")
        assert resp.status_code == 403
