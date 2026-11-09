"""A member donating from the portal: the gate, the amounts, and the sweep.

The sweep is the part worth the most attention. A donation receipt is raised
before the member reaches the gateway, so every change of mind leaves one
unpaid, and the one thing that must not happen is a member being chased for
money they decided not to give. The headline case is the opposite error:
``origin='donation'`` is also what an administrator's hand-raised donation
receipt carries, and that one is legitimately waiting for a bank transfer
(#434).
"""

from datetime import date, timedelta
from decimal import Decimal

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.billing.donation_service import (
    expire_unpaid_donations,
    suggested_donation_amounts,
)
from app.domains.billing.models import Receipt, Remittance
from app.domains.billing.service import mark_receipt_paid
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person

ON = {"member_donations_enabled": True}


def _org(db, features=None, *, message=None, locale="es"):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(
            id=1,
            name="Donation Test Club",
            currency="EUR",
            invoice_prefix="FAC",
            invoice_annual_reset=True,
            default_vat_rate=Decimal("21.00"),
        )
        db.add(org)
    org.locale = locale
    if features is not None:
        org.features = features
    if message is not None:
        org.donation_message = message
    db.flush()
    return org


def _tier(db, suffix):
    mtype = MembershipType(
        name=f"Donor tier {suffix}",
        slug=f"donor-tier-{suffix}",
        base_price=Decimal("0.00"),
        billing_frequency="annual",
        is_active=True,
    )
    db.add(mtype)
    db.flush()
    return mtype


def _member_user(db, suffix, *, status="active"):
    email = f"donor-{suffix}@example.test"
    person = Person(first_name="Dona", last_name=f"Donor{suffix}", email=email)
    db.add(person)
    db.flush()
    user = User(
        party_id=person.party_id,
        email=email,
        password_hash=hash_password("password123"),
        role="member",
        is_active=True,
    )
    db.add(user)
    db.flush()
    member = Member(
        party_id=person.party_id,
        membership_type_id=_tier(db, suffix).id,
        member_number=f"DON-{suffix}",
        status=status,
        is_active=True,
    )
    db.add(member)
    db.flush()
    return user, member


def _setup(db, suffix, *, features=None, message=None, locale="es", status="active"):
    _org(db, features if features is not None else dict(ON), message=message, locale=locale)
    return _member_user(db, suffix, status=status)


def _auth(user):
    return {"access_token": create_access_token(user.id)}


def _donate(client, user, amount):
    return client.post(
        "/api/v1/members/me/donations/",
        json={"amount": str(amount)},
        cookies=_auth(user),
    )


def _admin_raised_donation(db, member, *, due, number):
    """What a treasurer produces recording a donation already promised.

    ``origin='donation'`` through ``ReceiptCreate``, which accepts it, and
    ``donation_self_service`` left NULL because nothing but the donate endpoint
    sets it. This receipt is waiting for a bank transfer.
    """
    receipt = Receipt(
        receipt_number=number,
        party_id=member.party_id,
        origin="donation",
        description="Donativo prometido",
        base_amount=Decimal("500.00"),
        vat_rate=Decimal("0.00"),
        vat_amount=Decimal("0.00"),
        total_amount=Decimal("500.00"),
        status="emitted",
        emission_date=due - timedelta(days=30),
        due_date=due,
    )
    db.add(receipt)
    db.flush()
    return receipt


class TestTheGate:
    def test_the_options_are_absent_when_the_feature_is_off(self, client, db):
        user, _ = _setup(db, "gate-options", features={})
        db.commit()

        r = client.get("/api/v1/members/me/donations/options", cookies=_auth(user))

        # 404 and not 403: an instance that does not take donations should not
        # advertise that the feature exists.
        assert r.status_code == 404

    def test_donating_is_absent_when_the_feature_is_off(self, client, db):
        user, _ = _setup(db, "gate-post", features={})
        db.commit()

        assert _donate(client, user, 25).status_code == 404

    def test_an_explicit_false_is_off_too(self, client, db):
        user, _ = _setup(db, "gate-false", features={"member_donations_enabled": False})
        db.commit()

        assert _donate(client, user, 25).status_code == 404


class TestTheOptions:
    def test_the_defaults_are_served_when_nothing_is_configured(self, client, db):
        user, _ = _setup(db, "opt-default")
        db.commit()

        body = client.get(
            "/api/v1/members/me/donations/options", cookies=_auth(user)
        ).json()

        assert body["min_amount"] == 5
        assert body["max_amount"] == 1000
        assert body["suggested_amounts"] == [5, 10, 25, 50]
        # No ask written yet. The page has to render around its absence rather
        # than print an empty heading.
        assert body["message"] is None

    def test_the_configured_message_and_bounds_are_served(self, client, db):
        user, _ = _setup(
            db,
            "opt-set",
            features={**ON, "donation_min_amount": 10, "donation_max_amount": 60},
            message="Con tu donativo compramos material para los más pequeños.",
        )
        db.commit()

        body = client.get(
            "/api/v1/members/me/donations/options", cookies=_auth(user)
        ).json()

        assert body["message"].startswith("Con tu donativo")
        assert body["min_amount"] == 10
        assert body["max_amount"] == 60
        # 100 and 200 are off the ladder: the ceiling drops them.
        assert body["suggested_amounts"] == [10, 20, 50]

    def test_a_ceiling_below_the_floor_resolves_to_the_floor(self, client, db):
        """The save-side pair check only fires when one request carries both
        keys, so a row can hold this. The floor is the honest reading of it."""
        user, _ = _setup(
            db,
            "opt-inverted",
            features={**ON, "donation_min_amount": 50, "donation_max_amount": 10},
        )
        db.commit()

        body = client.get(
            "/api/v1/members/me/donations/options", cookies=_auth(user)
        ).json()

        assert body["min_amount"] == 50
        assert body["max_amount"] == 50
        assert body["suggested_amounts"] == [50]


class TestTheLadder:
    def test_it_scales_with_the_minimum(self):
        assert suggested_donation_amounts(1, 1000) == [1, 2, 5, 10]
        assert suggested_donation_amounts(5, 1000) == [5, 10, 25, 50]
        assert suggested_donation_amounts(50, 1000) == [50, 100, 250, 500]

    def test_the_minimum_always_survives_the_ceiling(self):
        assert suggested_donation_amounts(50, 50) == [50]


class TestDonating:
    def test_it_raises_an_emitted_donation_receipt(self, client, db):
        user, member = _setup(db, "raise")
        db.commit()

        r = _donate(client, user, 25)

        assert r.status_code == 201, r.text
        body = r.json()
        assert body["receipt_status"] == "emitted"
        assert Decimal(body["total_amount"]) == Decimal("25.00")

        receipt = db.query(Receipt).filter(Receipt.id == body["receipt_id"]).first()
        assert receipt.party_id == member.party_id
        assert receipt.origin == "donation"
        # No supply in return for it, so no tax on it by default (#432).
        assert receipt.vat_rate == Decimal("0.00")
        assert receipt.total_amount == Decimal("25.00")
        # The marker the sweep keys on, and the only writer of it.
        assert receipt.donation_self_service is True
        # Never collectable by direct debit: the mandate was signed for fees.
        assert receipt.is_batchable is False
        # The classification lives on `origin`; `concepts` is the chart of what
        # the club charges for, and a donation is not one of those.
        assert receipt.concept_id is None

    def test_the_line_follows_the_organisation_locale(self, client, db):
        user, _ = _setup(db, "locale-ca", locale="ca")
        db.commit()

        receipt_id = _donate(client, user, 10).json()["receipt_id"]

        receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
        assert receipt.description == "Donatiu"

    def test_an_amount_below_the_minimum_is_refused(self, client, db):
        user, _ = _setup(db, "too-small", features={**ON, "donation_min_amount": 10})
        db.commit()

        r = _donate(client, user, 5)

        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "donation_amount_out_of_range"
        assert r.json()["detail"]["min_amount"] == 10

    def test_an_amount_above_the_maximum_is_refused(self, client, db):
        """The bound exists so a typo cannot become a charge nobody meant, and
        it has to hold on the server: the amount arrives from the browser."""
        user, _ = _setup(db, "too-big", features={**ON, "donation_max_amount": 100})
        db.commit()

        r = _donate(client, user, 50000)

        assert r.status_code == 400
        assert r.json()["detail"]["max_amount"] == 100

    def test_zero_is_refused_by_the_schema(self, client, db):
        user, _ = _setup(db, "zero")
        db.commit()

        assert _donate(client, user, 0).status_code == 422

    def test_a_second_donation_leaves_the_first_alone(self, client, db):
        """Unlike a membership purchase, which voids the one it replaces. Two
        plans are contradictory; two donations are two donations."""
        user, member = _setup(db, "twice")
        db.commit()

        first = _donate(client, user, 10).json()["receipt_id"]
        second = _donate(client, user, 20).json()["receipt_id"]

        assert first != second
        statuses = {
            r.id: r.status
            for r in db.query(Receipt).filter(Receipt.id.in_([first, second]))
        }
        assert statuses == {first: "emitted", second: "emitted"}

    def test_the_member_can_see_it_among_their_own_receipts(self, client, db):
        user, _ = _setup(db, "visible")
        db.commit()
        receipt_id = _donate(client, user, 15).json()["receipt_id"]

        listed = client.get("/api/v1/members/me/receipts", cookies=_auth(user)).json()

        assert receipt_id in [item["id"] for item in listed["items"]]


class TestTheAbandonmentSweep:
    def test_an_unpaid_donation_is_voided_past_its_due_date(self, client, db):
        user, _ = _setup(db, "sweep-void")
        db.commit()
        receipt_id = _donate(client, user, 25).json()["receipt_id"]
        receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()

        assert expire_unpaid_donations(db, receipt.due_date + timedelta(days=1)) == 1
        db.refresh(receipt)
        assert receipt.status == "cancelled"

    def test_it_survives_up_to_and_including_its_due_date(self, client, db):
        user, _ = _setup(db, "sweep-notyet")
        db.commit()
        receipt_id = _donate(client, user, 25).json()["receipt_id"]
        receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()

        assert expire_unpaid_donations(db, receipt.due_date) == 0
        db.refresh(receipt)
        assert receipt.status == "emitted"

    def test_an_administrators_hand_raised_donation_is_never_touched(self, client, db):
        """The finding that decided the marker. A sweep keyed on
        ``origin == 'donation'`` would cancel this receipt the day after its
        due date, while the organisation is legitimately waiting for the
        transfer it records."""
        _, member = _setup(db, "sweep-admin")
        promised = _admin_raised_donation(
            db, member, due=date(2026, 3, 1), number="FAC-ADMIN-DON-1"
        )
        db.commit()

        assert expire_unpaid_donations(db, date(2026, 6, 1)) == 0
        db.refresh(promised)
        assert promised.status == "emitted"

    def test_a_paid_donation_is_never_touched(self, client, db):
        user, _ = _setup(db, "sweep-paid")
        db.commit()
        receipt_id = _donate(client, user, 25).json()["receipt_id"]
        receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
        mark_receipt_paid(db, receipt, payment_method="stripe_checkout")

        assert expire_unpaid_donations(db, receipt.due_date + timedelta(days=90)) == 0
        db.refresh(receipt)
        assert receipt.status == "paid"

    def test_a_receipt_handed_to_the_bank_is_never_touched(self, client, db):
        """A donation cannot enter a remittance (``is_batchable=False``), so
        this is belt and braces — but the predicate should say so rather than
        depend on another column staying as it is."""
        user, _ = _setup(db, "sweep-remittance")
        db.commit()
        receipt_id = _donate(client, user, 25).json()["receipt_id"]
        receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
        remittance = Remittance(
            remittance_number="REM-DON-1",
            remittance_type="sepa",
            status="submitted",
            emission_date=receipt.emission_date,
            due_date=receipt.due_date,
            total_amount=receipt.total_amount,
            receipt_count=1,
            creditor_name="Donation Test Club",
            creditor_iban="ES9121000418450200051332",
            creditor_id="ES12ZZZ00000000A",
        )
        db.add(remittance)
        db.flush()
        receipt.remittance_id = remittance.id
        db.flush()

        assert expire_unpaid_donations(db, receipt.due_date + timedelta(days=1)) == 0
        db.refresh(receipt)
        assert receipt.status == "emitted"

    def test_it_sweeps_even_once_the_feature_is_switched_off(self, client, db):
        """A club that stops taking donations still holds whatever it raised
        while it was on, and those must not become debts because a flag moved."""
        user, _ = _setup(db, "sweep-flag-off")
        db.commit()
        receipt_id = _donate(client, user, 25).json()["receipt_id"]
        receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
        org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
        org.features = {"member_donations_enabled": False}
        db.flush()

        assert expire_unpaid_donations(db, receipt.due_date + timedelta(days=1)) == 1
        db.refresh(receipt)
        assert receipt.status == "cancelled"
