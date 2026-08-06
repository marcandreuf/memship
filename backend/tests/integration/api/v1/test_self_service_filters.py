"""One test per result filter (§6.5).

Each of these routes serves both staff and members: the guard lets everyone in
and an inline branch narrows the rows. Getting one backwards is a disclosure
bug rather than a 403, so every filter gets its own named test asserting a
self-service account sees exactly its own record and nothing else.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.activities.models import Activity
from app.domains.billing.models import Receipt
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


def _cookie(user):
    return {"access_token": create_access_token(user.id)}


@pytest.fixture
def org(db):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(
            id=1, name="Test Club", locale="es", timezone="Europe/Madrid",
            currency="EUR", date_format="DD/MM/YYYY", brand_color="#0083ad",
        )
        db.add(org)
    db.flush()
    return org


@pytest.fixture
def membership_type(db):
    mt = MembershipType(
        name="Filter Standard", slug="filter-standard", base_price=10,
        billing_frequency="annual",
    )
    db.add(mt)
    db.flush()
    return mt


def _account(db, membership_type, email, role="member"):
    person = Person(first_name=email.split("@")[0], last_name="Filter", email=email)
    db.add(person)
    db.flush()
    from app.domains.auth.models import User

    user = User(
        person_id=person.id, email=email,
        password_hash=hash_password("password123"), role=role, is_active=True,
    )
    db.add(user)
    db.flush()
    member = Member(
        person_id=person.id, user_id=user.id,
        membership_type_id=membership_type.id, status="active",
    )
    db.add(member)
    db.flush()
    return user, member


@pytest.fixture
def mine(db, membership_type):
    return _account(db, membership_type, "mine-filter@test.com")


@pytest.fixture
def theirs(db, membership_type):
    return _account(db, membership_type, "theirs-filter@test.com")


@pytest.fixture
def staff(db, membership_type):
    return _account(db, membership_type, "staff-filter@test.com", role="admin")


class TestMembersDetailFilter:
    """members.py — holds members.read → any member; self only otherwise."""

    def test_self_service_account_reaches_its_own_record(self, client, db, org, mine):
        user, member = mine

        r = client.get(f"/api/v1/members/{member.id}", cookies=_cookie(user))

        assert r.status_code == 200

    def test_self_service_account_is_refused_another_record(self, client, db, org, mine, theirs):
        user, _ = mine
        _, other_member = theirs

        r = client.get(f"/api/v1/members/{other_member.id}", cookies=_cookie(user))

        assert r.status_code == 403

    def test_staff_reaches_any_record(self, client, db, org, staff, theirs):
        user, _ = staff
        _, other_member = theirs

        r = client.get(f"/api/v1/members/{other_member.id}", cookies=_cookie(user))

        assert r.status_code == 200


class TestMembersUpdateFilter:
    """members.py — the write half keys off members.write, not members.read."""

    def test_self_service_account_may_edit_itself(self, client, db, org, mine):
        user, member = mine

        r = client.put(
            f"/api/v1/members/{member.id}", json={"notes": "hi"}, cookies=_cookie(user)
        )

        assert r.status_code in (200, 422)

    def test_self_service_account_may_not_edit_another(self, client, db, org, mine, theirs):
        user, _ = mine
        _, other_member = theirs

        r = client.put(
            f"/api/v1/members/{other_member.id}", json={"notes": "hi"}, cookies=_cookie(user)
        )

        assert r.status_code == 403


class TestPersonsFilters:
    """persons.py — own person only, read and write halves separately."""

    def test_own_person_is_readable(self, client, db, org, mine):
        user, _ = mine

        r = client.get(f"/api/v1/persons/{user.person_id}", cookies=_cookie(user))

        assert r.status_code == 200

    def test_another_person_is_refused(self, client, db, org, mine, theirs):
        user, _ = mine
        other_user, _ = theirs

        r = client.get(f"/api/v1/persons/{other_user.person_id}", cookies=_cookie(user))

        assert r.status_code == 403

    def test_another_person_is_not_writable(self, client, db, org, mine, theirs):
        user, _ = mine
        other_user, _ = theirs

        r = client.put(
            f"/api/v1/persons/{other_user.person_id}",
            json={"first_name": "Hacked"},
            cookies=_cookie(user),
        )

        assert r.status_code == 403

    def test_staff_reads_any_person(self, client, db, org, staff, theirs):
        user, _ = staff
        other_user, _ = theirs

        r = client.get(f"/api/v1/persons/{other_user.person_id}", cookies=_cookie(user))

        assert r.status_code == 200


class TestActivitiesPublishedFilter:
    """activities.py — holds activities.read → drafts too; otherwise published only."""

    @pytest.fixture
    def draft_and_published(self, db):
        now = datetime.now(timezone.utc)
        common = {
            "starts_at": now + timedelta(days=10),
            "ends_at": now + timedelta(days=11),
            "registration_starts_at": now - timedelta(days=1),
            "registration_ends_at": now + timedelta(days=9),
            "max_participants": 50,
            "is_active": True,
        }
        draft = Activity(name="Secret Draft", slug="secret-draft", status="draft", **common)
        published = Activity(name="Open Day", slug="open-day", status="published", **common)
        db.add_all([draft, published])
        db.flush()
        return draft, published

    def test_self_service_account_never_sees_a_draft(
        self, client, db, org, mine, draft_and_published
    ):
        user, _ = mine
        draft, published = draft_and_published

        body = client.get("/api/v1/activities/", cookies=_cookie(user)).json()
        names = {a["name"] for a in (body if isinstance(body, list) else body["items"])}

        assert "Open Day" in names
        assert "Secret Draft" not in names

    def test_self_service_account_cannot_open_a_draft_by_id(
        self, client, db, org, mine, draft_and_published
    ):
        user, _ = mine
        draft, _ = draft_and_published

        r = client.get(f"/api/v1/activities/{draft.id}", cookies=_cookie(user))

        # 404, not 403: the route hides a draft's existence rather than
        # confirming it to someone who may not read it.
        assert r.status_code == 404

    def test_staff_sees_drafts(self, client, db, org, staff, draft_and_published):
        user, _ = staff
        draft, _ = draft_and_published

        r = client.get(f"/api/v1/activities/{draft.id}", cookies=_cookie(user))

        assert r.status_code == 200


class TestReceiptsOwnershipFilter:
    """receipts.py — holds billing.read → any receipt; own receipt otherwise."""

    @pytest.fixture
    def their_receipt(self, db, theirs):
        _, member = theirs
        receipt = Receipt(
            receipt_number="FAC-FILTER-1",
            member_id=member.id,
            origin="membership",
            description="Filter receipt",
            base_amount=Decimal("100.00"),
            vat_rate=Decimal("21.00"),
            vat_amount=Decimal("21.00"),
            total_amount=Decimal("121.00"),
            status="emitted",
            emission_date=date.today(),
        )
        db.add(receipt)
        db.flush()
        return receipt

    def test_self_service_account_cannot_download_another_receipt(
        self, client, db, org, mine, their_receipt
    ):
        user, _ = mine

        r = client.get(f"/api/v1/receipts/{their_receipt.id}/pdf", cookies=_cookie(user))

        assert r.status_code == 403

    def test_staff_may_read_any_receipt(self, client, db, org, staff, their_receipt):
        """Asserted on the detail route, not the PDF one: rendering needs
        WeasyPrint's GTK libraries, which are not installed everywhere."""
        user, _ = staff

        r = client.get(f"/api/v1/receipts/{their_receipt.id}", cookies=_cookie(user))

        assert r.status_code == 200


class TestCustomFieldsPersonFilter:
    """custom_fields.py — _resolve_person keys off members.read, not the tier."""

    def test_self_service_account_cannot_read_another_persons_values(
        self, client, db, org, mine, theirs
    ):
        org.features = {"custom_profile_fields": True}
        db.flush()
        user, _ = mine
        other_user, _ = theirs

        r = client.get(
            f"/api/v1/persons/{other_user.person_id}/custom-fields/", cookies=_cookie(user)
        )

        assert r.status_code == 403

    def test_staff_reads_another_persons_values(self, client, db, org, staff, theirs):
        org.features = {"custom_profile_fields": True}
        db.flush()
        user, _ = staff
        other_user, _ = theirs

        r = client.get(
            f"/api/v1/persons/{other_user.person_id}/custom-fields/", cookies=_cookie(user)
        )

        assert r.status_code == 200