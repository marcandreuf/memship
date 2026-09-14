"""What an account with no member record can and cannot reach.

A super admin or club admin administers the instance without belonging to the
club (#168), so it has no member row. That shape used to be impossible, and two
things follow from it that pull in opposite directions:

* every member-facing route has to refuse it cleanly rather than query a member
  that is not there;
* every route it shares with members has to keep working, because `self.*` is
  the *floor* on those — `members.py:152` and `receipts.py:312` admit the caller
  on `self.profile.read` / `self.billing.read` and then widen to "any member" on
  `members.read` / `billing.read`. A staff role holds the `self.*` keys
  (`ADMIN_SEED_KEYS` is the whole catalogue bar the reserved ones, and a super
  admin resolves to `ALL_KEYS`), so they are not what distinguishes the two.

The second half is the one worth guarding: taking `self.*` away from staff looks
like the tidy fix for the first half and would lock every admin out of the
member register, the receipt PDFs and the photo routes.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.billing.models import Receipt
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


def _cookie(user):
    return {"access_token": create_access_token(user.id)}


@pytest.fixture
def org(db):
    settings = db.query(OrganizationSettings).filter_by(id=1).first()
    if not settings:
        settings = OrganizationSettings(
            id=1, name="Test Club", locale="es", timezone="Europe/Madrid",
            currency="EUR", date_format="DD/MM/YYYY", brand_color="#0083ad",
        )
        db.add(settings)
    # The card routes 404 when the feature is off, which would make the
    # refusal test pass for entirely the wrong reason.
    settings.features = {"member_card": True}
    db.flush()
    return settings


@pytest.fixture
def membership_type(db):
    mt = MembershipType(
        name="No Member Standard", slug="no-member-standard",
        base_price=90, billing_frequency="annual",
    )
    db.add(mt)
    db.flush()
    return mt


@pytest.fixture
def operator(db):
    """A super admin the way the seed now creates one: no member record."""
    person = Person(first_name="Ops", last_name="Only", email="ops@examplee6e3b1.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id, email="ops@examplee6e3b1.com",
        password_hash=hash_password("password123"), role="super_admin", is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def club_admin(db):
    person = Person(first_name="Club", last_name="Admin", email="ca@examplee6e3b1.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id, email="ca@examplee6e3b1.com",
        password_hash=hash_password("password123"), role="admin", is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def joiner(db, membership_type):
    """An ordinary member, with a receipt, for the staff routes to act on."""
    person = Person(first_name="Real", last_name="Member", email="joiner@examplee6e3b1.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id, email="joiner@examplee6e3b1.com",
        password_hash=hash_password("password123"), role="member", is_active=True,
    )
    db.add(user)
    db.flush()
    member = Member(
        person_id=person.id, user_id=user.id,
        membership_type_id=membership_type.id, member_number="M-0001",
        status="active",
    )
    db.add(member)
    db.flush()
    receipt = Receipt(
        receipt_number="R-9001", member_id=member.id, origin="membership",
        description="Annual fee", base_amount=Decimal("90.00"),
        vat_rate=Decimal("0.00"), vat_amount=Decimal("0.00"),
        total_amount=Decimal("90.00"), status="emitted",
        emission_date=date(2026, 1, 10),
    )
    db.add(receipt)
    db.flush()
    return user, member, receipt


class TestTheSessionItself:
    def test_me_returns_the_account_with_null_member_fields(self, client, db, operator):
        r = client.get("/api/v1/auth/me", cookies=_cookie(operator))

        assert r.status_code == 200
        body = r.json()
        assert body["member_id"] is None
        assert body["member_number"] is None
        assert body["member_status"] is None

    def test_it_still_holds_the_self_namespace(self, client, db, operator):
        """Not a quirk to clean up later — see the module docstring. This is
        what admits staff to the routes they share with members."""
        body = client.get("/api/v1/auth/me", cookies=_cookie(operator)).json()

        assert {"self.profile.read", "self.billing.read"} <= set(body["permissions"])

    def test_the_roles_say_operator_not_member(self, client, db, operator):
        body = client.get("/api/v1/auth/me", cookies=_cookie(operator)).json()

        assert {r["slug"] for r in body["roles"]} == {"super_admin"}


class TestMemberFacingRoutesRefuseIt:
    """One refusal, one code, so a caller can tell this from a real failure."""

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/members/me/receipts",
            "/api/v1/members/me/membership/quote/{membership_type_id}",
            "/api/v1/me/card",
        ],
    )
    def test_they_answer_403_not_a_member(
        self, client, db, org, operator, membership_type, path
    ):
        r = client.get(
            path.format(membership_type_id=membership_type.id),
            cookies=_cookie(operator),
        )

        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "not_a_member"

    def test_none_of_them_raise(self, client, db, org, operator, membership_type):
        """The failure this guards is a 500 from querying a member that is not
        there, which is what the old code would have done."""
        for path in (
            "/api/v1/members/me/receipts",
            f"/api/v1/members/me/membership/quote/{membership_type.id}",
            "/api/v1/me/card",
            "/api/v1/me/card/qr.svg",
        ):
            r = client.get(path, cookies=_cookie(operator))
            assert r.status_code < 500, f"{path} returned {r.status_code}"

    def test_a_club_admin_is_refused_the_same_way(self, client, db, org, club_admin):
        r = client.get("/api/v1/members/me/receipts", cookies=_cookie(club_admin))

        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "not_a_member"


class TestStaffRoutesKeepWorking:
    """The regression the obvious fix would cause.

    Every one of these is gated on a `self.*` key and widened by an
    administrative one, so they break the moment `self.*` stops being granted to
    staff — with a 403 from the dependency, before the handler runs.
    """

    def test_it_can_read_a_member(self, client, db, org, operator, joiner):
        _, member, _ = joiner

        r = client.get(f"/api/v1/members/{member.id}", cookies=_cookie(operator))

        assert r.status_code == 200
        assert r.json()["member_number"] == "M-0001"

    def test_it_can_list_the_register(self, client, db, org, operator, joiner):
        r = client.get("/api/v1/members/", cookies=_cookie(operator))

        assert r.status_code == 200

    def test_it_can_download_a_receipt_pdf(self, client, db, org, operator, joiner):
        _, _, receipt = joiner

        r = client.get(f"/api/v1/receipts/{receipt.id}/pdf", cookies=_cookie(operator))

        assert r.status_code == 200

    def test_a_club_admin_can_read_a_member_too(self, client, db, org, club_admin, joiner):
        _, member, _ = joiner

        r = client.get(f"/api/v1/members/{member.id}", cookies=_cookie(club_admin))

        assert r.status_code == 200


class TestItIsOutsideTheClub:
    def test_the_register_does_not_list_it(self, client, db, org, operator, joiner):
        body = client.get("/api/v1/members/", cookies=_cookie(operator)).json()

        emails = {row["email"] for row in body["items"] if row.get("email")}
        assert "ops@examplee6e3b1.com" not in emails

    def test_the_count_excludes_it(self, db, org, operator, club_admin, joiner):
        assert db.query(Member).count() == 1

    def test_a_billing_run_raises_nothing_for_it(self, db, org, operator, membership_type, joiner):
        """The real exposure in the issue: an operator active on a paid tier is
        inside the population a membership-fee run charges."""
        from app.domains.billing.schemas import GenerateMembershipFeesRequest
        from app.domains.billing.service import generate_membership_fees

        receipts = generate_membership_fees(
            db,
            GenerateMembershipFeesRequest(
                billing_period_start=date(2027, 1, 1),
                billing_period_end=date(2027, 12, 31),
                emission_date=date(2027, 1, 1),
                due_date=date(2027, 1, 31),
            ),
            created_by_id=operator.id,
        )

        billed = {r.member_id for r in receipts}
        operator_members = {
            m.id for m in db.query(Member).filter(Member.user_id == operator.id).all()
        }
        assert operator_members == set()
        assert billed and operator_members.isdisjoint(billed)
