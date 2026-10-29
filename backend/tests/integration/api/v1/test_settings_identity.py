"""The settings API after the Phase 5c split: same contract, party-backed.

Every field name `GET/PUT /settings` spoke before the split it still speaks;
what changed is where the values live — the club's party row, its contact
rows, its primary bank account. These tests hold the contract AND check the
rows, because the contract alone would pass with the old columns too.
"""

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import BankAccount, Contact, Party, Person


def _create_user(db, role="admin", suffix=""):
    person = Person(
        first_name="Settings", last_name=f"Admin{suffix}",
        email=f"settings-{role}{suffix}@examplee6e3b1.com",
    )
    db.add(person)
    db.flush()
    user = User(
        party_id=person.party_id,
        email=f"settings-{role}{suffix}@examplee6e3b1.com",
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id)}


def _ensure_org(db):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(
            id=1, name="Club Base", locale="es", timezone="Europe/Madrid",
            currency="EUR", date_format="DD/MM/YYYY",
        )
        db.add(org)
        db.flush()
    return org


class TestIdentityWritesReachTheParty:
    def test_renaming_the_club_cannot_drift(self, client, db):
        org = _ensure_org(db)
        admin = _create_user(db, suffix="idn1")

        resp = client.put(
            "/api/v1/settings/",
            json={"name": "Club Renombrado", "tax_id": "G11111111",
                  "legal_name": "Club Renombrado SL"},
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Club Renombrado"

        party = db.query(Party).filter(Party.id == org.party_id).first()
        db.refresh(party)
        assert party.display_name == "Club Renombrado"
        assert party.national_id == "G11111111"
        assert party.legal_name == "Club Renombrado SL"

    def test_phone_and_website_are_contact_rows(self, client, db):
        org = _ensure_org(db)
        admin = _create_user(db, suffix="idn2")
        cookies = _auth_cookie(admin)

        resp = client.put(
            "/api/v1/settings/",
            json={"phone": "+34 600 222 333", "website": "https://idn2.example"},
            cookies=cookies,
        )
        assert resp.status_code == 200
        assert resp.json()["phone"] == "+34 600 222 333"
        assert resp.json()["website"] == "https://idn2.example"

        rows = dict(
            db.query(Contact.channel, Contact.value)
            .filter(Contact.party_id == org.party_id, Contact.is_primary.is_(True))
            .all()
        )
        assert rows["phone"] == "+34 600 222 333"
        assert rows["url"] == "https://idn2.example"

        # Clearing removes the row rather than leaving an empty value
        resp = client.put("/api/v1/settings/", json={"phone": ""}, cookies=cookies)
        assert resp.status_code == 200
        assert resp.json()["phone"] is None
        remaining = (
            db.query(Contact)
            .filter(Contact.party_id == org.party_id, Contact.channel == "phone")
            .count()
        )
        assert remaining == 0

    def test_the_collection_account_is_a_bank_accounts_row(self, client, db):
        org = _ensure_org(db)
        admin = _create_user(db, suffix="idn3")

        resp = client.put(
            "/api/v1/settings/",
            json={"bank_name": "CaixaBank",
                  "bank_iban": "ES9121000418450200051332",
                  "bank_bic": "CAIXESBBXXX"},
            cookies=_auth_cookie(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["bank_iban"] == "ES9121000418450200051332"

        account = (
            db.query(BankAccount)
            .filter(BankAccount.party_id == org.party_id, BankAccount.is_primary.is_(True))
            .one()
        )
        assert account.bank_name == "CaixaBank"
        assert account.iban == "ES9121000418450200051332"
        assert account.bic == "CAIXESBBXXX"

    def test_branding_serves_the_party_backed_fields(self, client, db):
        _ensure_org(db)
        admin = _create_user(db, suffix="idn4")
        client.put(
            "/api/v1/settings/",
            json={"name": "Club Branding idn4", "website": "https://idn4.example"},
            cookies=_auth_cookie(admin),
        )

        body = client.get("/api/v1/settings/branding").json()
        assert body["name"] == "Club Branding idn4"
        assert body["website"] == "https://idn4.example"


class TestEntityLegalName:
    def test_round_trips_through_the_entities_api(self, client, db):
        admin = _create_user(db, suffix="eln1")
        cookies = _auth_cookie(admin)

        created = client.post(
            "/api/v1/entities/",
            json={"kind": "company", "name": "Mercantil SL eln1",
                  "legal_name": "Mercantil Sociedad Limitada"},
            cookies=cookies,
        )
        assert created.status_code == 201
        assert created.json()["legal_name"] == "Mercantil Sociedad Limitada"

        updated = client.put(
            f"/api/v1/entities/{created.json()['id']}",
            json={"legal_name": "Mercantil S.L.U."},
            cookies=cookies,
        )
        assert updated.status_code == 200
        assert updated.json()["legal_name"] == "Mercantil S.L.U."
        assert updated.json()["name"] == "Mercantil SL eln1"
