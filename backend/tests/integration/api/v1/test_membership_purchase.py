"""The member-facing endpoints for buying a membership plan."""

from datetime import date
from decimal import Decimal

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.billing.models import Receipt
from app.domains.members.models import Member, MembershipType
from app.domains.members.schemas import MemberSelfUpdate
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


def _org(db):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if org:
        return org
    org = OrganizationSettings(
        id=1,
        name="Buy API Club",
        currency="EUR",
        invoice_prefix="FAC",
        invoice_annual_reset=True,
        default_vat_rate=Decimal("21.00"),
    )
    db.add(org)
    db.flush()
    return org


def _tier(db, suffix, price, frequency="annual", is_active=True):
    mtype = MembershipType(
        name=f"API Tier {suffix}",
        slug=f"api-tier-{suffix}",
        base_price=Decimal(str(price)),
        billing_frequency=frequency,
        is_active=is_active,
    )
    db.add(mtype)
    db.flush()
    return mtype


def _member_user(db, suffix, tier, status="active"):
    email = f"api-buy-{suffix}@example.test"
    person = Person(first_name="Api", last_name=f"Buyer{suffix}", email=email)
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=email,
        password_hash=hash_password("password123"),
        role="member",
        is_active=True,
    )
    db.add(user)
    db.flush()
    member = Member(
        person_id=person.id,
        user_id=user.id,
        membership_type_id=tier.id,
        member_number=f"API-{suffix}",
        status=status,
        is_active=True,
    )
    db.add(member)
    db.flush()
    return user, member


def _setup(db, suffix, *, price=200, frequency="annual", status="active"):
    _org(db)
    free = _tier(db, f"free-{suffix}", 0)
    paid = _tier(db, f"paid-{suffix}", price, frequency)
    user, member = _member_user(db, suffix, free, status=status)
    return user, member, free, paid


def _auth(user):
    return {"access_token": create_access_token(user.id)}


class TestQuote:
    def test_returns_the_tax_inclusive_total(self, client, db):
        user, _, _, paid = _setup(db, "quote", price=200)
        db.commit()

        r = client.get(
            f"/api/v1/members/me/membership/quote/{paid.id}", cookies=_auth(user)
        )

        assert r.status_code == 200
        data = r.json()
        assert Decimal(data["full_price"]) == Decimal("200.00")
        # The portal shows `total_amount`; `base_amount` is the pre-tax figure
        # the plan advertises, which the receipt would otherwise contradict.
        assert Decimal(data["total_amount"]) == (
            Decimal(data["base_amount"]) + Decimal(data["vat_amount"])
        )
        assert Decimal(data["vat_rate"]) == Decimal("21.00")
        assert data["billing_frequency"] == "annual"
        assert data["months_in_period"] == 12

    def test_quoting_raises_no_receipt(self, client, db):
        user, member, _, paid = _setup(db, "quotenoreceipt")
        db.commit()

        client.get(
            f"/api/v1/members/me/membership/quote/{paid.id}", cookies=_auth(user)
        )

        assert db.query(Receipt).filter(Receipt.member_id == member.id).count() == 0

    def test_unknown_plan_is_404(self, client, db):
        user, _, _, _ = _setup(db, "quote404")
        db.commit()

        r = client.get(
            "/api/v1/members/me/membership/quote/99999", cookies=_auth(user)
        )

        assert r.status_code == 404


class TestPurchase:
    def test_raises_a_receipt_and_leaves_the_tier_alone(self, client, db):
        user, member, free, paid = _setup(db, "purchase")
        db.commit()

        r = client.post(
            "/api/v1/members/me/membership/purchase",
            json={"membership_type_id": paid.id},
            cookies=_auth(user),
        )

        assert r.status_code == 201
        data = r.json()
        assert data["membership_type_id"] == paid.id
        assert data["receipt_status"] == "emitted"

        receipt = db.query(Receipt).filter(Receipt.id == data["receipt_id"]).one()
        assert receipt.member_id == member.id
        assert receipt.purchased_membership_type_id == paid.id
        db.refresh(member)
        assert member.membership_type_id == free.id

    def test_the_receipt_id_is_what_checkout_takes(self, client, db):
        user, _, _, paid = _setup(db, "checkout")
        db.commit()

        r = client.post(
            "/api/v1/members/me/membership/purchase",
            json={"membership_type_id": paid.id},
            cookies=_auth(user),
        )
        receipt_id = r.json()["receipt_id"]

        # No Stripe provider is configured, so the checkout endpoint stops on
        # that rather than on ownership or a status it will not accept — which
        # is the part this asserts: the purchase hands checkout a receipt it
        # recognises as the caller's and as payable.
        checkout = client.post(
            f"/api/v1/receipts/{receipt_id}/stripe/checkout", cookies=_auth(user)
        )
        assert checkout.status_code == 400
        assert "Stripe provider" in checkout.json()["detail"]

    def test_another_members_purchase_is_not_payable(self, client, db):
        user, _, _, paid = _setup(db, "owner")
        stranger_user, _ = _member_user(db, "stranger", paid)
        db.commit()

        r = client.post(
            "/api/v1/members/me/membership/purchase",
            json={"membership_type_id": paid.id},
            cookies=_auth(user),
        )
        receipt_id = r.json()["receipt_id"]

        checkout = client.post(
            f"/api/v1/receipts/{receipt_id}/stripe/checkout",
            cookies=_auth(stranger_user),
        )
        assert checkout.status_code == 403

    def test_buying_twice_leaves_one_live_receipt(self, client, db):
        user, member, _, paid = _setup(db, "twice")
        other = _tier(db, "twice-other", 300)
        db.commit()

        first = client.post(
            "/api/v1/members/me/membership/purchase",
            json={"membership_type_id": paid.id},
            cookies=_auth(user),
        ).json()
        second = client.post(
            "/api/v1/members/me/membership/purchase",
            json={"membership_type_id": other.id},
            cookies=_auth(user),
        ).json()

        live = (
            db.query(Receipt)
            .filter(
                Receipt.member_id == member.id,
                Receipt.status != "cancelled",
            )
            .all()
        )
        assert [r.id for r in live] == [second["receipt_id"]]
        assert first["receipt_id"] != second["receipt_id"]

    def test_the_plan_already_held_is_refused(self, client, db):
        _org(db)
        paid = _tier(db, "already", 100)
        user, _ = _member_user(db, "already", paid)
        db.commit()

        r = client.post(
            "/api/v1/members/me/membership/purchase",
            json={"membership_type_id": paid.id},
            cookies=_auth(user),
        )

        assert r.status_code == 400

    def test_a_retired_plan_is_refused(self, client, db):
        user, _, _, _ = _setup(db, "retired")
        retired = _tier(db, "retired-plan", 100, is_active=False)
        db.commit()

        r = client.post(
            "/api/v1/members/me/membership/purchase",
            json={"membership_type_id": retired.id},
            cookies=_auth(user),
        )

        assert r.status_code == 400

    def test_a_sign_up_awaiting_approval_is_refused(self, client, db):
        user, _, _, paid = _setup(db, "unapproved", status="pending")
        db.commit()

        r = client.post(
            "/api/v1/members/me/membership/purchase",
            json={"membership_type_id": paid.id},
            cookies=_auth(user),
        )

        assert r.status_code == 403

    def test_anonymous_callers_are_rejected(self, client, db):
        _, _, _, paid = _setup(db, "anon")
        db.commit()

        r = client.post(
            "/api/v1/members/me/membership/purchase",
            json={"membership_type_id": paid.id},
        )

        assert r.status_code == 401


class TestSelfUpdateStillGuarded:
    def test_a_member_cannot_write_their_own_tier(self, client, db):
        """The purchase endpoint exists because this stays closed."""
        assert "membership_type_id" not in MemberSelfUpdate.model_fields

        user, member, free, paid = _setup(db, "selfupdate")
        db.commit()

        r = client.put(
            f"/api/v1/members/{member.id}",
            json={"membership_type_id": paid.id},
            cookies=_auth(user),
        )

        assert r.status_code == 403
        assert "membership_type_id" in r.json()["detail"]
        db.refresh(member)
        assert member.membership_type_id == free.id


class TestActivationThroughTheAdminPaidRoute:
    def test_an_admin_recording_cash_grants_the_plan(self, client, db):
        user, member, free, paid = _setup(db, "cash")
        admin_person = Person(
            first_name="Admin", last_name="Cash", email="api-buy-admin@example.test"
        )
        db.add(admin_person)
        db.flush()
        admin = User(
            person_id=admin_person.id,
            email=admin_person.email,
            password_hash=hash_password("password123"),
            role="admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()

        purchase = client.post(
            "/api/v1/members/me/membership/purchase",
            json={"membership_type_id": paid.id},
            cookies=_auth(user),
        ).json()
        db.refresh(member)
        assert member.membership_type_id == free.id

        r = client.post(
            f"/api/v1/receipts/{purchase['receipt_id']}/pay",
            json={"payment_method": "cash", "payment_date": date.today().isoformat()},
            cookies=_auth(admin),
        )

        assert r.status_code == 200
        db.refresh(member)
        assert member.membership_type_id == paid.id
