"""Integration tests for recurring billing — run-now, run history, scheduling."""

from datetime import date

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.billing.models import BillingRun, Receipt
from app.domains.billing.recurring_billing_service import (
    run_scheduled_billing,
)
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


def _create_user(db, role="admin", suffix="brun"):
    person = Person(first_name="Test", last_name="User", email=f"{suffix}-{role}@examplee6e3b1.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=f"{suffix}-{role}@examplee6e3b1.com",
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id)}


def _ensure_org_settings(db, features=None):
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


def _create_member(db, frequency="monthly", suffix="m1", price=50.00):
    person = Person(
        first_name="María", last_name="García", email=f"maria-{suffix}@examplee6e3b1.com"
    )
    db.add(person)
    db.flush()
    mtype = MembershipType(
        name=f"Member {suffix}",
        slug=f"type-{suffix}",
        base_price=price,
        billing_frequency=frequency,
    )
    db.add(mtype)
    db.flush()
    member = Member(
        person_id=person.id,
        membership_type_id=mtype.id,
        member_number=f"M-{suffix}",
        status="active",
    )
    db.add(member)
    db.flush()
    return member


def _membership_receipt_count(db):
    return (
        db.query(Receipt)
        .filter(Receipt.origin == "membership", Receipt.is_active.is_(True))
        .count()
    )


# --- Run now ---


class TestRunNow:
    def test_run_now_monthly_generates_receipts(self, client, db):
        user = _create_user(db, "admin", "rn-monthly")
        _ensure_org_settings(db)
        _create_member(db, "monthly", "rn1")
        _create_member(db, "monthly", "rn2")

        resp = client.post(
            "/api/v1/billing-runs/run-now",
            json={"frequency": "monthly"},
            cookies=_auth_cookie(user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["receipts_generated"] == 2
        assert len(data["runs"]) == 1
        assert data["runs"][0]["frequency"] == "monthly"
        assert data["runs"][0]["status"] == "success"
        assert _membership_receipt_count(db) == 2

    def test_run_now_forbidden_for_member(self, client, db):
        user = _create_user(db, "member", "rn-forbidden")
        _ensure_org_settings(db)
        resp = client.post(
            "/api/v1/billing-runs/run-now",
            json={"frequency": "monthly"},
            cookies=_auth_cookie(user),
        )
        assert resp.status_code == 403

    def test_run_now_dedup_second_run_zero(self, client, db):
        user = _create_user(db, "admin", "rn-dedup")
        _ensure_org_settings(db)
        _create_member(db, "monthly", "dd1")

        first = client.post(
            "/api/v1/billing-runs/run-now",
            json={"frequency": "monthly"},
            cookies=_auth_cookie(user),
        )
        assert first.json()["receipts_generated"] == 1

        second = client.post(
            "/api/v1/billing-runs/run-now",
            json={"frequency": "monthly"},
            cookies=_auth_cookie(user),
        )
        assert second.status_code == 200
        # Dedup invariant: no new receipt created, and still a single run row for
        # the period (re-running returns the existing successful run).
        assert _membership_receipt_count(db) == 1
        assert db.query(BillingRun).filter(BillingRun.frequency == "monthly").count() == 1

    def test_run_now_only_bills_matching_frequency(self, client, db):
        user = _create_user(db, "admin", "rn-freq")
        _ensure_org_settings(db)
        _create_member(db, "monthly", "freq-m")
        _create_member(db, "annual", "freq-a")

        resp = client.post(
            "/api/v1/billing-runs/run-now",
            json={"frequency": "monthly"},
            cookies=_auth_cookie(user),
        )
        # Only the monthly member is billed; the annual member is not
        assert resp.json()["receipts_generated"] == 1
        assert _membership_receipt_count(db) == 1

    def test_run_now_all_frequencies(self, client, db):
        user = _create_user(db, "admin", "rn-all")
        _ensure_org_settings(db)
        _create_member(db, "monthly", "all-m")
        _create_member(db, "annual", "all-a")

        resp = client.post(
            "/api/v1/billing-runs/run-now",
            json={},
            cookies=_auth_cookie(user),
        )
        assert resp.status_code == 200
        data = resp.json()
        # monthly + quarterly + annual runs created; quarterly has no members
        assert len(data["runs"]) == 3
        assert data["receipts_generated"] == 2

    def test_run_now_rejects_one_time(self, client, db):
        user = _create_user(db, "admin", "rn-onetime")
        _ensure_org_settings(db)
        resp = client.post(
            "/api/v1/billing-runs/run-now",
            json={"frequency": "one_time"},
            cookies=_auth_cookie(user),
        )
        assert resp.status_code == 422


# --- Run history ---


class TestRunHistory:
    def test_list_billing_runs(self, client, db):
        user = _create_user(db, "admin", "list-runs")
        _ensure_org_settings(db)
        _create_member(db, "monthly", "lr1")
        client.post(
            "/api/v1/billing-runs/run-now",
            json={"frequency": "monthly"},
            cookies=_auth_cookie(user),
        )

        resp = client.get("/api/v1/billing-runs", cookies=_auth_cookie(user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert body["items"][0]["frequency"] == "monthly"

    def test_list_filter_by_frequency(self, client, db):
        user = _create_user(db, "admin", "list-filter")
        _ensure_org_settings(db)
        _create_member(db, "monthly", "lf-m")
        _create_member(db, "annual", "lf-a")
        client.post(
            "/api/v1/billing-runs/run-now", json={}, cookies=_auth_cookie(user)
        )

        resp = client.get(
            "/api/v1/billing-runs?frequency=annual", cookies=_auth_cookie(user)
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["frequency"] == "annual"

    def test_list_forbidden_for_member(self, client, db):
        user = _create_user(db, "member", "list-forbidden")
        _ensure_org_settings(db)
        resp = client.get("/api/v1/billing-runs", cookies=_auth_cookie(user))
        assert resp.status_code == 403

    def test_get_billing_run_detail(self, client, db):
        user = _create_user(db, "admin", "detail-run")
        _ensure_org_settings(db)
        _create_member(db, "monthly", "dr1")
        run = client.post(
            "/api/v1/billing-runs/run-now",
            json={"frequency": "monthly"},
            cookies=_auth_cookie(user),
        ).json()["runs"][0]

        resp = client.get(
            f"/api/v1/billing-runs/{run['id']}", cookies=_auth_cookie(user)
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == run["id"]
        assert resp.json()["receipts_generated"] == 1

    def test_get_billing_run_404(self, client, db):
        user = _create_user(db, "admin", "detail-404")
        _ensure_org_settings(db)
        resp = client.get("/api/v1/billing-runs/999999", cookies=_auth_cookie(user))
        assert resp.status_code == 404


# --- Scheduled path (service-level) ---


class TestScheduledBilling:
    def test_disabled_returns_empty(self, db):
        _ensure_org_settings(db, features={"recurring_billing_enabled": False})
        _create_member(db, "monthly", "sch-disabled")
        assert run_scheduled_billing(db, today=date(2026, 6, 1)) == []

    def test_runs_due_frequency(self, db):
        _ensure_org_settings(
            db, features={"recurring_billing_enabled": True, "recurring_billing_day": 1}
        )
        _create_member(db, "monthly", "sch-due")
        # June 1: monthly due, quarterly/annual not (June isn't a quarter start)
        runs = run_scheduled_billing(db, today=date(2026, 6, 1))
        assert len(runs) == 1
        assert runs[0].frequency == "monthly"
        assert runs[0].triggered_by == "scheduled"
        assert runs[0].receipts_generated == 1

    def test_skips_when_day_mismatch(self, db):
        _ensure_org_settings(
            db, features={"recurring_billing_enabled": True, "recurring_billing_day": 1}
        )
        _create_member(db, "monthly", "sch-mismatch")
        assert run_scheduled_billing(db, today=date(2026, 6, 2)) == []

    def test_quarter_start_runs_monthly_and_quarterly(self, db):
        _ensure_org_settings(
            db, features={"recurring_billing_enabled": True, "recurring_billing_day": 1}
        )
        _create_member(db, "monthly", "qs-m")
        _create_member(db, "quarterly", "qs-q")
        # April 1: monthly + quarterly due, annual not
        runs = run_scheduled_billing(db, today=date(2026, 4, 1))
        freqs = {r.frequency for r in runs}
        assert freqs == {"monthly", "quarterly"}


# --- Notification email ---


class TestNotificationEmail:
    def test_notify_sends_when_configured(self, db, monkeypatch):
        _ensure_org_settings(
            db, features={"billing_notification_email": "admin@examplee6e3b1.com"}
        )
        sent = {}

        def fake_send_email(to, subject, html_body):
            sent["to"] = to
            sent["subject"] = subject
            return True

        monkeypatch.setattr("app.core.email.send_email", fake_send_email)

        from app.tasks.billing_tasks import _notify_admin

        runs = [BillingRun(frequency="monthly", receipts_generated=3, status="success")]
        _notify_admin(db, runs)
        assert sent.get("to") == "admin@examplee6e3b1.com"

    def test_notify_noop_when_not_configured(self, db, monkeypatch):
        _ensure_org_settings(db, features={})
        called = {"n": 0}

        def fake_send_email(to, subject, html_body):
            called["n"] += 1
            return True

        monkeypatch.setattr("app.core.email.send_email", fake_send_email)

        from app.tasks.billing_tasks import _notify_admin

        runs = [BillingRun(frequency="monthly", receipts_generated=3, status="success")]
        _notify_admin(db, runs)
        assert called["n"] == 0
