"""The §6.4 branding split.

`GET /settings` was reachable by any authenticated user because the portal
shell reads the club's name, logo and feature flags from it — which also handed
every member the bank IBAN, the invoice counters and the SEPA creditor id. The
split moves the shell onto a public subset and puts the rest behind
`settings.read`.
"""

import pytest

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person

# Everything the shell renders. Losing one of these silently breaks the header,
# the theme, or a feature flag, with no error anywhere.
SHELL_FIELDS = {
    "name",
    "logo_url",
    "brand_color",
    "locale",
    "timezone",
    "currency",
    "date_format",
    "features",
}

# The reason the split exists.
WITHHELD_FIELDS = {
    "tax_id",
    "bank_name",
    "bank_iban",
    "bank_bic",
    "invoice_prefix",
    "invoice_next_number",
    "creditor_id",
    "sepa_format",
    "custom_settings",
}


def _cookie(user):
    return {"access_token": create_access_token(user.id)}


@pytest.fixture
def org(db):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(id=1, name="Branding Club")
        db.add(org)
    org.locale = "es"
    org.timezone = "Europe/Madrid"
    org.currency = "EUR"
    org.date_format = "DD/MM/YYYY"
    org.brand_color = "#0083ad"
    org.bank_iban = "ES9121000418450200051332"
    org.tax_id = "B12345678"
    org.creditor_id = "ES12ZZZ12345678"
    org.features = {"member_card": True}
    db.flush()
    return org


@pytest.fixture
def membership_type(db):
    mt = db.query(MembershipType).filter_by(slug="branding-standard").first()
    if not mt:
        mt = MembershipType(
            name="Branding Standard", slug="branding-standard",
            base_price=10, billing_frequency="annual",
        )
        db.add(mt)
        db.flush()
    return mt


def _account(db, membership_type, email, role="member"):
    from app.domains.auth.models import User

    person = Person(first_name=email.split("@")[0], last_name="Branding", email=email)
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id, email=email,
        password_hash=hash_password("password123"), role=role, is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        Member(
            person_id=person.id, user_id=user.id,
            membership_type_id=membership_type.id, status="active",
        )
    )
    db.flush()
    return user


@pytest.fixture
def member(db, membership_type):
    return _account(db, membership_type, "branding-member@examplee6e3b1.com")


@pytest.fixture
def staff(db, membership_type):
    return _account(db, membership_type, "branding-staff@examplee6e3b1.com", role="admin")


class TestBrandingIsPublic:
    def test_no_authentication_needed(self, client, db, org):
        r = client.get("/api/v1/settings/branding")

        assert r.status_code == 200
        assert r.json()["name"] == "Branding Club"

    def test_carries_everything_the_shell_renders(self, client, db, org):
        body = client.get("/api/v1/settings/branding").json()

        assert SHELL_FIELDS <= set(body)
        assert body["features"] == {"member_card": True}

    def test_withholds_the_administrative_fields(self, client, db, org):
        body = client.get("/api/v1/settings/branding").json()

        assert not (WITHHELD_FIELDS & set(body)), (
            f"branding leaked {sorted(WITHHELD_FIELDS & set(body))}"
        )


class TestFullSettingsIsGuarded:
    def test_a_member_is_refused(self, client, db, org, member):
        r = client.get("/api/v1/settings/", cookies=_cookie(member))

        assert r.status_code == 403

    def test_staff_holding_settings_read_gets_the_full_record(
        self, client, db, org, staff
    ):
        r = client.get("/api/v1/settings/", cookies=_cookie(staff))

        assert r.status_code == 200
        assert r.json()["bank_iban"] == "ES9121000418450200051332"

    def test_the_address_route_moved_with_it(self, client, db, org, member):
        r = client.get("/api/v1/settings/address", cookies=_cookie(member))

        assert r.status_code == 403
