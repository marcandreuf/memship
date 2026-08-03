"""Integration tests for payment reminders — overdue transition, schedule, sending."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.billing.models import PaymentProvider, Receipt, ReceiptReminder
from app.domains.billing.reminder_service import (
    mark_overdue,
    reminders_due,
    run_scheduled_reminders,
    send_reminder,
)
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person

TODAY = date(2026, 6, 15)
_UNSET = object()


def _create_user(db, role="admin", suffix="rem"):
    person = Person(first_name="Test", last_name="User", email=f"{suffix}-{role}@test.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=f"{suffix}-{role}@test.com",
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


def _create_member(db, suffix="m1", email=_UNSET):
    person = Person(
        first_name="María",
        last_name="García",
        email=f"maria-{suffix}@test.com" if email is _UNSET else email,
    )
    db.add(person)
    db.flush()
    mtype = MembershipType(name=f"Member {suffix}", slug=f"type-{suffix}", base_price=50.00)
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


def _create_receipt(db, member, suffix="r1", status="emitted", due_date=None, paid=False):
    receipt = Receipt(
        receipt_number=f"R-{suffix}",
        member_id=member.id,
        origin="membership",
        description="Membership fee",
        base_amount=Decimal("50.00"),
        vat_rate=Decimal("0.00"),
        vat_amount=Decimal("0.00"),
        total_amount=Decimal("50.00"),
        status=status,
        emission_date=date(2026, 6, 1),
        due_date=due_date,
        payment_date=TODAY if paid else None,
    )
    db.add(receipt)
    db.flush()
    return receipt


def _add_reminder(db, receipt, sent_at, status="sent", number=1):
    rem = ReceiptReminder(
        receipt_id=receipt.id,
        reminder_number=number,
        channel="email",
        status=status,
        to_email="x@test.com",
        triggered_by="scheduled",
        sent_at=sent_at,
    )
    db.add(rem)
    db.flush()
    return rem


def _patch_email_sent(monkeypatch, ok=True):
    monkeypatch.setattr("app.core.email.send_email", lambda to, subject, html_body: ok)


def _capture_reminder_email(monkeypatch):
    """Capture the kwargs passed to ``send_payment_reminder_email`` (Pay-Now vs bank).

    Returns a dict that ``send_reminder`` fills in on the next call.
    """
    captured = {}

    def _fake(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(
        "app.domains.billing.reminder_service.send_payment_reminder_email", _fake
    )
    return captured


# --- Overdue transition ---


class TestMarkOverdue:
    def test_flips_emitted_past_due(self, db):
        member = _create_member(db, "mo1")
        r = _create_receipt(db, member, "mo1", "emitted", due_date=TODAY - timedelta(days=1))
        assert mark_overdue(db, TODAY) == 1
        db.refresh(r)
        assert r.status == "overdue"

    def test_leaves_not_yet_due(self, db):
        member = _create_member(db, "mo2")
        r = _create_receipt(db, member, "mo2", "emitted", due_date=TODAY + timedelta(days=5))
        assert mark_overdue(db, TODAY) == 0
        db.refresh(r)
        assert r.status == "emitted"

    def test_ignores_paid_receipt(self, db):
        member = _create_member(db, "mo3")
        r = _create_receipt(
            db, member, "mo3", "emitted", due_date=TODAY - timedelta(days=10), paid=True
        )
        assert mark_overdue(db, TODAY) == 0
        db.refresh(r)
        assert r.status == "emitted"


# --- Schedule logic ---


class TestRemindersDue:
    def test_first_reminder_after_days_after_due(self, db):
        member = _create_member(db, "rd1")
        # due 3 days ago, days_after_due=3 → due today
        _create_receipt(db, member, "rd1", "overdue", due_date=TODAY - timedelta(days=3))
        due = reminders_due(db, TODAY, days_after_due=3, repeat_days=7, max_count=3)
        assert len(due) == 1

    def test_not_due_before_days_after_due(self, db):
        member = _create_member(db, "rd2")
        # due 1 day ago, days_after_due=3 → not yet
        _create_receipt(db, member, "rd2", "overdue", due_date=TODAY - timedelta(days=1))
        due = reminders_due(db, TODAY, days_after_due=3, repeat_days=7, max_count=3)
        assert due == []

    def test_repeat_cadence_due_after_repeat_days(self, db):
        member = _create_member(db, "rd3")
        r = _create_receipt(db, member, "rd3", "overdue", due_date=TODAY - timedelta(days=20))
        # last reminder 8 days ago, repeat=7 → due again
        _add_reminder(db, r, datetime(2026, 6, 7, tzinfo=timezone.utc))
        due = reminders_due(db, TODAY, 3, 7, 3)
        assert [x.id for x in due] == [r.id]

    def test_repeat_cadence_not_due_within_repeat_days(self, db):
        member = _create_member(db, "rd3b")
        r = _create_receipt(db, member, "rd3b", "overdue", due_date=TODAY - timedelta(days=20))
        # last reminder 3 days ago, repeat=7 → not yet
        _add_reminder(db, r, datetime(2026, 6, 12, tzinfo=timezone.utc))
        assert reminders_due(db, TODAY, 3, 7, 3) == []

    def test_stops_at_max_count(self, db):
        member = _create_member(db, "rd4")
        r = _create_receipt(db, member, "rd4", "overdue", due_date=TODAY - timedelta(days=40))
        for i, d in enumerate([1, 8, 15], start=1):
            _add_reminder(db, r, datetime(2026, 5, d, tzinfo=timezone.utc), number=i)
        # 3 sent, max 3 → not due
        assert reminders_due(db, TODAY, 3, 7, 3) == []

    def test_one_per_day_guard(self, db):
        member = _create_member(db, "rd5")
        r = _create_receipt(db, member, "rd5", "overdue", due_date=TODAY - timedelta(days=20))
        # reminder already sent today → skip even though repeat elapsed
        _add_reminder(db, r, datetime(2026, 6, 15, 8, tzinfo=timezone.utc))
        assert reminders_due(db, TODAY, 3, 7, 3) == []


# --- Sending ---


class TestSendReminder:
    def test_writes_sent_row(self, db, monkeypatch):
        _patch_email_sent(monkeypatch, ok=True)
        _ensure_org_settings(db)
        member = _create_member(db, "sr1")
        r = _create_receipt(db, member, "sr1", "overdue", due_date=TODAY - timedelta(days=5))
        reminder = send_reminder(db, r, "manual", user_id=None, today=TODAY)
        assert reminder.status == "sent"
        assert reminder.reminder_number == 1
        assert reminder.to_email == "maria-sr1@test.com"

    def test_records_failed_when_no_transport(self, db, monkeypatch):
        _patch_email_sent(monkeypatch, ok=False)
        _ensure_org_settings(db)
        member = _create_member(db, "sr2")
        r = _create_receipt(db, member, "sr2", "overdue", due_date=TODAY - timedelta(days=5))
        reminder = send_reminder(db, r, "scheduled", today=TODAY)
        assert reminder.status == "failed"

    def test_raises_when_no_email(self, db):
        _ensure_org_settings(db)
        member = _create_member(db, "sr3", email=None)
        r = _create_receipt(db, member, "sr3", "overdue", due_date=TODAY - timedelta(days=5))
        try:
            send_reminder(db, r, "manual", today=TODAY)
            assert False, "expected ValueError"
        except ValueError:
            pass


# --- Pay-Now link vs bank-transfer fallback (T7) ---


class TestPayNowLink:
    def test_pay_now_link_when_online_provider_active(self, db, monkeypatch):
        captured = _capture_reminder_email(monkeypatch)
        _ensure_org_settings(db)
        db.add(
            PaymentProvider(
                provider_type="stripe", display_name="Stripe", status="active"
            )
        )
        db.flush()
        member = _create_member(db, "pn1")
        r = _create_receipt(db, member, "pn1", "overdue", due_date=TODAY - timedelta(days=5))
        send_reminder(db, r, "manual", today=TODAY)
        assert captured["pay_now_url"] is not None
        assert captured["bank_details"] is None

    def test_bank_fallback_when_no_provider(self, db, monkeypatch):
        captured = _capture_reminder_email(monkeypatch)
        org = _ensure_org_settings(db)
        org.bank_name = "Caixa Test"
        org.bank_iban = "ES9121000418450200051332"
        db.flush()
        member = _create_member(db, "pn2")
        r = _create_receipt(db, member, "pn2", "overdue", due_date=TODAY - timedelta(days=5))
        send_reminder(db, r, "manual", today=TODAY)
        assert captured["pay_now_url"] is None
        assert captured["bank_details"] is not None
        assert "ES9121000418450200051332" in captured["bank_details"]


# --- Scheduled orchestration ---


class TestRunScheduled:
    def test_disabled_noop(self, db):
        _ensure_org_settings(db, features={"payment_reminders_enabled": False})
        member = _create_member(db, "rs1")
        _create_receipt(db, member, "rs1", "emitted", due_date=TODAY - timedelta(days=10))
        summary = run_scheduled_reminders(db, today=TODAY)
        assert summary == {"overdue_marked": 0, "reminders_sent": 0, "failures": 0}

    def test_marks_and_sends(self, db, monkeypatch):
        _patch_email_sent(monkeypatch, ok=True)
        _ensure_org_settings(
            db,
            features={
                "payment_reminders_enabled": True,
                "reminder_days_after_due": 3,
                "reminder_repeat_days": 7,
                "reminder_max_count": 3,
            },
        )
        member = _create_member(db, "rs2")
        _create_receipt(db, member, "rs2", "emitted", due_date=TODAY - timedelta(days=10))
        summary = run_scheduled_reminders(db, today=TODAY)
        assert summary["overdue_marked"] == 1
        assert summary["reminders_sent"] == 1
        assert summary["failures"] == 0


# --- Manual endpoint ---


class TestManualEndpoint:
    def test_send_reminder_ok(self, client, db, monkeypatch):
        _patch_email_sent(monkeypatch, ok=True)
        _ensure_org_settings(db)
        user = _create_user(db, "admin", "me1")
        member = _create_member(db, "me1")
        r = _create_receipt(db, member, "me1", "overdue", due_date=TODAY - timedelta(days=5))
        resp = client.post(
            f"/api/v1/receipts/{r.id}/send-reminder", cookies=_auth_cookie(user)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "sent"
        assert resp.json()["triggered_by"] == "manual"

    def test_send_forbidden_for_member(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "member", "me2")
        member = _create_member(db, "me2")
        r = _create_receipt(db, member, "me2", "overdue", due_date=TODAY - timedelta(days=5))
        resp = client.post(
            f"/api/v1/receipts/{r.id}/send-reminder", cookies=_auth_cookie(user)
        )
        assert resp.status_code == 403

    def test_send_409_when_not_payable(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "admin", "me3")
        member = _create_member(db, "me3")
        r = _create_receipt(db, member, "me3", "paid", due_date=TODAY - timedelta(days=5))
        resp = client.post(
            f"/api/v1/receipts/{r.id}/send-reminder", cookies=_auth_cookie(user)
        )
        assert resp.status_code == 409

    def test_send_409_when_max_reached(self, client, db, monkeypatch):
        _patch_email_sent(monkeypatch, ok=True)
        _ensure_org_settings(db, features={"reminder_max_count": 2})
        user = _create_user(db, "admin", "me4")
        member = _create_member(db, "me4")
        r = _create_receipt(db, member, "me4", "overdue", due_date=TODAY - timedelta(days=5))
        _add_reminder(db, r, datetime(2026, 6, 1, tzinfo=timezone.utc), number=1)
        _add_reminder(db, r, datetime(2026, 6, 8, tzinfo=timezone.utc), number=2)
        resp = client.post(
            f"/api/v1/receipts/{r.id}/send-reminder", cookies=_auth_cookie(user)
        )
        assert resp.status_code == 409

    def test_list_reminders(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "admin", "me5")
        member = _create_member(db, "me5")
        r = _create_receipt(db, member, "me5", "overdue", due_date=TODAY - timedelta(days=5))
        _add_reminder(db, r, datetime(2026, 6, 10, tzinfo=timezone.utc), number=1)
        resp = client.get(
            f"/api/v1/receipts/{r.id}/reminders", cookies=_auth_cookie(user)
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["reminder_number"] == 1

    def test_list_reminders_404(self, client, db):
        _ensure_org_settings(db)
        user = _create_user(db, "admin", "me6")
        resp = client.get("/api/v1/receipts/999999/reminders", cookies=_auth_cookie(user))
        assert resp.status_code == 404
