"""Integration tests for the annual summary reports endpoint."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.activities.models import Activity, Registration
from app.domains.auth.models import User
from app.domains.billing.models import Receipt
from app.domains.members.models import Member, MembershipType
from app.domains.persons.models import Person

YEAR = 2026


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id)}


def _admin(db, suffix):
    person = Person(first_name="Admin", last_name="User", email=f"admin-rep-{suffix}@examplee6e3b1.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=f"admin-rep-{suffix}@examplee6e3b1.com",
        password_hash=hash_password("password123"),
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _member(db, suffix, *, status="active", joined_at=None, status_changed_at=None, with_user=False,
            membership_type_id=None, is_active=True):
    person = Person(first_name="Mem", last_name=f"Ber-{suffix}", email=f"m-rep-{suffix}@examplee6e3b1.com")
    db.add(person)
    db.flush()
    uid = None
    role_user = None
    if with_user:
        role_user = User(
            person_id=person.id,
            email=f"m-rep-{suffix}@examplee6e3b1.com",
            password_hash=hash_password("password123"),
            role="member",
            is_active=True,
        )
        db.add(role_user)
        db.flush()
        uid = role_user.id
    member = Member(
        person_id=person.id,
        user_id=uid,
        member_number=f"M-rep-{suffix}",
        status=status,
        joined_at=joined_at or date(YEAR, 1, 1),
        status_changed_at=status_changed_at,
        membership_type_id=membership_type_id,
        is_active=is_active,
    )
    db.add(member)
    db.flush()
    return (member, role_user) if with_user else member


def _receipt(db, member, *, suffix, status, emission_date, payment_date=None, total="121.00"):
    receipt = Receipt(
        receipt_number=f"FAC-rep-{suffix}",
        member_id=member.id,
        origin="membership",
        description=f"Receipt {suffix}",
        base_amount=Decimal("100.00"),
        vat_rate=Decimal("21.00"),
        vat_amount=Decimal("21.00"),
        total_amount=Decimal(total),
        status=status,
        emission_date=emission_date,
        payment_date=payment_date,
    )
    db.add(receipt)
    db.flush()
    return receipt


def _activity(db, suffix, starts_at):
    activity = Activity(
        name=f"Act {suffix}",
        slug=f"act-rep-{suffix}",
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=2),
        registration_starts_at=starts_at - timedelta(days=30),
        registration_ends_at=starts_at - timedelta(days=1),
        max_participants=50,
        status="published",
        is_active=True,
    )
    db.add(activity)
    db.flush()
    return activity


def _registration(db, activity, member, status="confirmed"):
    reg = Registration(activity_id=activity.id, member_id=member.id, status=status)
    db.add(reg)
    db.flush()
    return reg


class TestAnnualSummary:
    def test_revenue_and_outstanding_by_month(self, client, db):
        admin = _admin(db, "rev")
        member = _member(db, "rev-m")
        # Paid in March (revenue index 2), outstanding emitted in June (index 5)
        _receipt(db, member, suffix="paid-mar", status="paid",
                 emission_date=date(YEAR, 3, 1), payment_date=date(YEAR, 3, 15))
        _receipt(db, member, suffix="emit-jun", status="emitted",
                 emission_date=date(YEAR, 6, 10))
        client.cookies.update(_auth_cookie(admin))

        resp = client.get(f"/api/v1/reports/annual-summary?year={YEAR}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["year"] == YEAR
        assert len(data["revenue_by_month"]) == 12
        assert data["revenue_by_month"][2] == 121.0
        assert sum(data["revenue_by_month"]) == 121.0
        assert data["outstanding_by_month"][5] == 121.0
        assert sum(data["outstanding_by_month"]) == 121.0

    def test_new_members_and_net_growth(self, client, db):
        admin = _admin(db, "grow")
        # 3 new members joined this year (active)
        _member(db, "g1", joined_at=date(YEAR, 2, 5))
        _member(db, "g2", joined_at=date(YEAR, 2, 20))
        _member(db, "g3", joined_at=date(YEAR, 5, 1))
        # 1 member that joined last year and was cancelled this year (lost, not new)
        _member(db, "lost", status="cancelled", joined_at=date(YEAR - 1, 4, 1),
                status_changed_at=datetime(YEAR, 3, 10, tzinfo=timezone.utc))
        client.cookies.update(_auth_cookie(admin))

        resp = client.get(f"/api/v1/reports/annual-summary?year={YEAR}")
        data = resp.json()
        assert data["new_members_by_month"][1] == 2  # February
        assert data["new_members_by_month"][4] == 1  # May
        assert data["new_members"] == 3
        assert data["lost_members"] == 1
        assert data["net_growth"] == 2
        assert data["active_members"] == 3
        assert data["total_members"] == 4

    def test_participation_ordering(self, client, db):
        admin = _admin(db, "part")
        a_big = _activity(db, "big", datetime(YEAR, 4, 1, tzinfo=timezone.utc))
        a_small = _activity(db, "small", datetime(YEAR, 4, 2, tzinfo=timezone.utc))
        # big: 2 confirmed; small: 1 confirmed; plus a cancelled (ignored)
        for i in range(2):
            _registration(db, a_big, _member(db, f"pb{i}"), status="confirmed")
        _registration(db, a_small, _member(db, "ps0"), status="confirmed")
        _registration(db, a_small, _member(db, "ps-cxl"), status="cancelled")
        client.cookies.update(_auth_cookie(admin))

        resp = client.get(f"/api/v1/reports/annual-summary?year={YEAR}")
        parts = resp.json()["activity_participation"]
        assert [p["activity_name"] for p in parts] == ["Act big", "Act small"]
        assert parts[0]["count"] == 2
        assert parts[1]["count"] == 1

    def test_empty_year_zeroed(self, client, db):
        admin = _admin(db, "empty")
        client.cookies.update(_auth_cookie(admin))

        resp = client.get(f"/api/v1/reports/annual-summary?year=2099")
        data = resp.json()
        assert data["revenue_by_month"] == [0.0] * 12
        assert data["outstanding_by_month"] == [0.0] * 12
        assert data["new_members_by_month"] == [0] * 12
        assert data["new_members"] == 0
        assert data["net_growth"] == 0
        assert data["activity_participation"] == []

    def test_defaults_to_current_year(self, client, db):
        admin = _admin(db, "default")
        client.cookies.update(_auth_cookie(admin))

        resp = client.get("/api/v1/reports/annual-summary")
        assert resp.status_code == 200
        assert resp.json()["year"] == date.today().year

    def test_non_admin_forbidden(self, client, db):
        _member(db, "forbidden", with_user=True)
        member, user = _member(db, "forbidden2", with_user=True)
        client.cookies.update(_auth_cookie(user))

        resp = client.get(f"/api/v1/reports/annual-summary?year={YEAR}")
        assert resp.status_code == 403


def _tier(db, suffix, price, *, frequency="monthly"):
    mtype = MembershipType(
        name=f"Tier {suffix}",
        slug=f"tier-rep-{suffix}",
        base_price=Decimal(str(price)),
        billing_frequency=frequency,
        is_active=True,
    )
    db.add(mtype)
    db.flush()
    return mtype


class TestPaidTierWithoutPurchase:
    """Who the sign-up bug parked on a priced tier, and who merely looks like it."""

    URL = "/api/v1/reports/paid-tier-without-purchase"

    def test_a_paid_tier_with_no_receipts_at_all_is_listed(self, client, db):
        admin = _admin(db, "ptp-plain")
        tier = _tier(db, "plain", 50)
        member = _member(db, "ptp-plain", membership_type_id=tier.id)
        client.cookies.update(_auth_cookie(admin))

        resp = client.get(self.URL)

        assert resp.status_code == 200
        rows = {r["member_id"]: r for r in resp.json()["items"]}
        assert member.id in rows
        assert rows[member.id]["membership_type_name"] == "Tier plain"
        assert rows[member.id]["base_price"] == 50.0
        assert rows[member.id]["unpaid_receipts"] == 0
        assert rows[member.id]["unpaid_amount"] == 0.0

    def test_a_free_tier_and_a_missing_tier_are_not_damage(self, client, db):
        admin = _admin(db, "ptp-free")
        free = _tier(db, "free", 0)
        on_free = _member(db, "ptp-free", membership_type_id=free.id)
        on_nothing = _member(db, "ptp-none")
        client.cookies.update(_auth_cookie(admin))

        resp = client.get(self.URL)

        listed = {r["member_id"] for r in resp.json()["items"]}
        assert on_free.id not in listed
        assert on_nothing.id not in listed

    def test_a_settled_membership_receipt_clears_the_member(self, client, db):
        """Money that arrived against a membership fee is the purchase."""
        admin = _admin(db, "ptp-paid")
        tier = _tier(db, "paid", 50)
        member = _member(db, "ptp-paid", membership_type_id=tier.id)
        _receipt(db, member, suffix="ptp-paid", status="paid",
                 emission_date=date(YEAR, 3, 1), payment_date=date(YEAR, 3, 15))
        client.cookies.update(_auth_cookie(admin))

        resp = client.get(self.URL)

        assert member.id not in {r["member_id"] for r in resp.json()["items"]}

    def test_unpaid_membership_receipts_are_counted_not_excused(self, client, db):
        """Being billed already is the damage, not evidence of a purchase."""
        admin = _admin(db, "ptp-unpaid")
        tier = _tier(db, "unpaid", 50)
        member = _member(db, "ptp-unpaid", membership_type_id=tier.id)
        _receipt(db, member, suffix="ptp-emit", status="emitted",
                 emission_date=date(YEAR, 4, 1))
        _receipt(db, member, suffix="ptp-over", status="overdue",
                 emission_date=date(YEAR, 5, 1))
        _receipt(db, member, suffix="ptp-cxl", status="cancelled",
                 emission_date=date(YEAR, 6, 1))
        client.cookies.update(_auth_cookie(admin))

        resp = client.get(self.URL)

        row = next(r for r in resp.json()["items"] if r["member_id"] == member.id)
        assert row["unpaid_receipts"] == 2
        assert row["unpaid_amount"] == 242.0

    def test_members_the_club_has_closed_are_left_out(self, client, db):
        admin = _admin(db, "ptp-closed")
        tier = _tier(db, "closed", 50)
        cancelled = _member(db, "ptp-cxl", status="cancelled", membership_type_id=tier.id)
        expired = _member(db, "ptp-exp", status="expired", membership_type_id=tier.id)
        deactivated = _member(db, "ptp-off", membership_type_id=tier.id, is_active=False)
        pending = _member(db, "ptp-pend", status="pending", membership_type_id=tier.id)
        client.cookies.update(_auth_cookie(admin))

        resp = client.get(self.URL)

        listed = {r["member_id"] for r in resp.json()["items"]}
        assert cancelled.id not in listed
        assert expired.id not in listed
        assert deactivated.id not in listed
        assert pending.id in listed

    def test_the_dearest_tier_comes_first(self, client, db):
        admin = _admin(db, "ptp-order")
        cheap = _tier(db, "cheap", 10)
        dear = _tier(db, "dear", 90)
        on_cheap = _member(db, "ptp-cheap", membership_type_id=cheap.id)
        on_dear = _member(db, "ptp-dear", membership_type_id=dear.id)
        client.cookies.update(_auth_cookie(admin))

        resp = client.get(self.URL)

        ordered = [r["member_id"] for r in resp.json()["items"]]
        assert ordered.index(on_dear.id) < ordered.index(on_cheap.id)

    def test_a_member_account_cannot_read_it(self, client, db):
        _member(db, "ptp-forbidden", with_user=True)
        _, user = _member(db, "ptp-forbidden2", with_user=True)
        client.cookies.update(_auth_cookie(user))

        resp = client.get(self.URL)

        assert resp.status_code == 403
