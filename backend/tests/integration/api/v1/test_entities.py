"""Integration tests for entity (non-person party) endpoints."""

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import Role, RolePermission, User, UserRoleAssignment
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Contact, ContactType, Party, Person


def _create_user(db, role="admin", suffix=""):
    person = Person(
        first_name="Entity", last_name=f"Admin{suffix}",
        email=f"entity-{role}{suffix}@examplee6e3b1.com",
    )
    db.add(person)
    db.flush()
    user = User(
        party_id=person.party_id,
        email=f"entity-{role}{suffix}@examplee6e3b1.com",
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _user_with(db, keys, *, slug):
    """A user holding exactly one custom role granting exactly `keys`."""
    role = Role(slug=slug, name=slug.title(), is_system=False)
    db.add(role)
    db.flush()
    for key in sorted(keys):
        db.add(RolePermission(role_id=role.id, permission_key=key))
    email = f"{slug}@examplee6e3b1.com"
    person = Person(first_name="Custom", last_name="Staff", email=email)
    db.add(person)
    db.flush()
    user = User(
        party_id=person.party_id, email=email,
        password_hash=hash_password("password123"), is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(UserRoleAssignment(user_id=user.id, role_id=role.id))
    db.flush()
    return user


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id)}


def _ensure_org_settings(db):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(
            id=1, name="Club Test", locale="es", timezone="Europe/Madrid",
            currency="EUR", date_format="DD/MM/YYYY", invoice_prefix="FAC",
            invoice_next_number=1, invoice_annual_reset=True, default_vat_rate=21.00,
        )
        db.add(org)
        db.flush()
    return org


def _entity_payload(**overrides):
    base = {
        "kind": "company",
        "name": "Acme SL",
        "national_id": "B12345678",
        "email": "info@acme-sl.example",
    }
    base.update(overrides)
    return base


class TestEntityCRUD:
    def test_create_and_get(self, client, db):
        admin = _create_user(db, suffix="ent-c1")
        resp = client.post(
            "/api/v1/entities/", json=_entity_payload(), cookies=_auth_cookie(admin)
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["kind"] == "company"
        assert data["name"] == "Acme SL"
        assert data["national_id"] == "B12345678"

        got = client.get(f"/api/v1/entities/{data['id']}", cookies=_auth_cookie(admin))
        assert got.status_code == 200
        assert got.json()["name"] == "Acme SL"

        # The party row carries the name as display_name
        party = db.query(Party).filter(Party.id == data["id"]).first()
        assert party.kind == "company"
        assert party.display_name == "Acme SL"

    def test_create_refuses_person_and_unknown_kinds(self, client, db):
        admin = _create_user(db, suffix="ent-c2")
        for kind in ("person", "cooperative"):
            resp = client.post(
                "/api/v1/entities/",
                json=_entity_payload(kind=kind, name=f"Bad {kind}"),
                cookies=_auth_cookie(admin),
            )
            assert resp.status_code == 400, kind

    def test_list_search_and_kind_filter(self, client, db):
        admin = _create_user(db, suffix="ent-l1")
        cookies = _auth_cookie(admin)
        client.post("/api/v1/entities/", json=_entity_payload(
            name="Fundación Lumen ent-l1", kind="foundation", national_id="G0001l1",
            email="lumen-l1@example.org"), cookies=cookies)
        client.post("/api/v1/entities/", json=_entity_payload(
            name="Ayuntamiento Sur ent-l1", kind="public_body", national_id="P0002l1",
            email="sur-l1@example.org"), cookies=cookies)

        resp = client.get("/api/v1/entities/?search=Lumen ent-l1", cookies=cookies)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert [i["name"] for i in items] == ["Fundación Lumen ent-l1"]

        resp = client.get(
            "/api/v1/entities/?kind=public_body&search=ent-l1", cookies=cookies
        )
        assert [i["name"] for i in resp.json()["items"]] == ["Ayuntamiento Sur ent-l1"]

        # Search matches national_id too
        resp = client.get("/api/v1/entities/?search=G0001l1", cookies=cookies)
        assert [i["national_id"] for i in resp.json()["items"]] == ["G0001l1"]

    def test_person_party_is_not_an_entity(self, client, db):
        admin = _create_user(db, suffix="ent-p1")
        person = Person(first_name="Juan", last_name="Pérez ent-p1")
        db.add(person)
        db.flush()
        resp = client.get(
            f"/api/v1/entities/{person.party_id}", cookies=_auth_cookie(admin)
        )
        assert resp.status_code == 404

    def test_club_party_is_not_an_entity(self, client, db):
        org = _ensure_org_settings(db)
        admin = _create_user(db, suffix="ent-club1")
        cookies = _auth_cookie(admin)

        resp = client.get(f"/api/v1/entities/{org.party_id}", cookies=cookies)
        assert resp.status_code == 404

        resp = client.get("/api/v1/entities/?per_page=100", cookies=cookies)
        assert org.party_id not in [i["id"] for i in resp.json()["items"]]

    def test_update(self, client, db):
        admin = _create_user(db, suffix="ent-u1")
        cookies = _auth_cookie(admin)
        created = client.post(
            "/api/v1/entities/", json=_entity_payload(name="Vieja SL ent-u1"),
            cookies=cookies,
        ).json()

        resp = client.put(
            f"/api/v1/entities/{created['id']}",
            json={"name": "Nueva Fundación ent-u1", "kind": "foundation"},
            cookies=cookies,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Nueva Fundación ent-u1"
        assert data["kind"] == "foundation"
        # Untouched fields survive a partial update
        assert data["national_id"] == "B12345678"

        resp = client.put(
            f"/api/v1/entities/{created['id']}", json={"kind": "person"},
            cookies=cookies,
        )
        assert resp.status_code == 400

    def test_delete(self, client, db):
        admin = _create_user(db, suffix="ent-d1")
        cookies = _auth_cookie(admin)
        created = client.post(
            "/api/v1/entities/", json=_entity_payload(name="Efímera SL ent-d1"),
            cookies=cookies,
        ).json()

        resp = client.delete(f"/api/v1/entities/{created['id']}", cookies=cookies)
        assert resp.status_code == 204
        assert client.get(
            f"/api/v1/entities/{created['id']}", cookies=cookies
        ).status_code == 404

    def test_delete_refuses_with_financial_history(self, client, db):
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="ent-d2")
        cookies = _auth_cookie(admin)
        created = client.post(
            "/api/v1/entities/", json=_entity_payload(name="Donante SL ent-d2"),
            cookies=cookies,
        ).json()

        # A donation: a manual receipt addressed to the entity's party
        receipt = client.post(
            "/api/v1/receipts/",
            json={
                "party_id": created["id"],
                "origin": "manual",
                "description": "Donación anual",
                "base_amount": 500,
                "vat_rate": 0,
                "emission_date": "2026-10-01",
            },
            cookies=cookies,
        )
        assert receipt.status_code == 201

        resp = client.delete(f"/api/v1/entities/{created['id']}", cookies=cookies)
        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert detail["code"] == "entity_has_history"
        assert detail["receipts"] == 1


class TestEntityKinds:
    def test_lists_only_non_natural_kinds(self, client, db):
        admin = _create_user(db, suffix="ent-k1")
        resp = client.get("/api/v1/entities/kinds", cookies=_auth_cookie(admin))
        assert resp.status_code == 200
        codes = [k["code"] for k in resp.json()]
        assert "person" not in codes
        assert {"company", "association", "public_body", "foundation", "other"} <= set(codes)


class TestEntityPermissions:
    def test_member_role_is_refused(self, client, db):
        member_user = _create_user(db, role="member", suffix="ent-perm1")
        cookies = _auth_cookie(member_user)
        assert client.get("/api/v1/entities/", cookies=cookies).status_code == 403
        assert client.post(
            "/api/v1/entities/", json=_entity_payload(), cookies=cookies
        ).status_code == 403

    def test_entities_only_custom_role_suffices(self, client, db):
        _ensure_org_settings(db)
        user = _user_with(
            db, {"entities.read", "entities.write"}, slug="entities-manager-ent"
        )
        cookies = _auth_cookie(user)
        created = client.post(
            "/api/v1/entities/", json=_entity_payload(name="Gestora SL ent-cr1"),
            cookies=cookies,
        )
        assert created.status_code == 201
        assert client.get("/api/v1/entities/", cookies=cookies).status_code == 200
        # ...but it grants nothing about members
        assert client.get("/api/v1/members/", cookies=cookies).status_code == 403


class TestEntityAddress:
    def test_put_creates_then_updates(self, client, db):
        admin = _create_user(db, suffix="ent-a1")
        cookies = _auth_cookie(admin)
        created = client.post(
            "/api/v1/entities/", json=_entity_payload(name="Con Sede SL ent-a1"),
            cookies=cookies,
        ).json()

        assert client.get(
            f"/api/v1/entities/{created['id']}/address", cookies=cookies
        ).json() is None

        resp = client.put(
            f"/api/v1/entities/{created['id']}/address",
            json={"address_line1": "Calle Mayor 1", "city": "Madrid",
                  "postal_code": "28001"},
            cookies=cookies,
        )
        assert resp.status_code == 200
        assert resp.json()["address_line1"] == "Calle Mayor 1"

        resp = client.put(
            f"/api/v1/entities/{created['id']}/address",
            json={"address_line1": "Calle Menor 2", "city": "Madrid"},
            cookies=cookies,
        )
        assert resp.status_code == 200

        got = client.get(
            f"/api/v1/entities/{created['id']}/address", cookies=cookies
        ).json()
        assert got["address_line1"] == "Calle Menor 2"


class TestEntityContacts:
    def test_a_new_primary_demotes_the_entitys_incumbent(self, client, db):
        """The fourth write path onto ``uq_contacts_one_primary_per_channel``,
        and the one not in the review. The demotion lives on the session rather
        than at the call sites, so this route inherited it from phase 3 without
        a line of its own -- which is what this pins."""
        admin = _create_user(db, suffix="ent-prim")
        cookies = _auth_cookie(admin)
        entity = client.post(
            "/api/v1/entities/", json=_entity_payload(name="Primaria SL ent-prim"),
            cookies=cookies,
        ).json()
        home = db.query(ContactType).filter(ContactType.code == "phone_home").first()
        if not home:
            home = ContactType(code="phone_home", name="Home Phone", channel="phone", is_active=True)
            db.add(home)
        mobile = db.query(ContactType).filter(ContactType.code == "phone_mobile").first()
        if not mobile:
            mobile = ContactType(code="phone_mobile", name="Mobile Phone", channel="phone", is_active=True)
            db.add(mobile)
        db.flush()
        incumbent = Contact(
            party_id=entity["id"], contact_type_id=home.id,
            value="900 000 010", is_primary=True,
        )
        db.add(incumbent)
        db.flush()

        resp = client.post(
            f"/api/v1/parties/{entity['id']}/contacts/",
            json={"contact_type_id": mobile.id, "value": "600 000 010", "is_primary": True},
            cookies=cookies,
        )

        assert resp.status_code == 201
        assert resp.json()["is_primary"] is True
        db.refresh(incumbent)
        assert incumbent.is_primary is False

    def test_crud_scoped_by_party(self, client, db):
        admin = _create_user(db, suffix="ent-ct1")
        cookies = _auth_cookie(admin)
        created = client.post(
            "/api/v1/entities/", json=_entity_payload(name="Contactable SL ent-ct1"),
            cookies=cookies,
        ).json()

        resp = client.post(
            f"/api/v1/parties/{created['id']}/contacts/",
            json={"value": "entidad-ct1@example.org", "label": "Secretaría"},
            cookies=cookies,
        )
        assert resp.status_code == 201
        contact_id = resp.json()["id"]

        listed = client.get(
            f"/api/v1/parties/{created['id']}/contacts/", cookies=cookies
        )
        assert [c["id"] for c in listed.json()] == [contact_id]

        resp = client.put(
            f"/api/v1/contacts/{contact_id}",
            json={"label": "Gerencia"},
            cookies=cookies,
        )
        assert resp.status_code == 200
        assert resp.json()["label"] == "Gerencia"

        assert client.delete(
            f"/api/v1/contacts/{contact_id}", cookies=cookies
        ).status_code == 204

    def test_person_party_404s_on_party_routes(self, client, db):
        admin = _create_user(db, suffix="ent-ct2")
        person = Person(first_name="Ana", last_name="López ent-ct2")
        db.add(person)
        db.flush()
        resp = client.get(
            f"/api/v1/parties/{person.party_id}/contacts/", cookies=_auth_cookie(admin)
        )
        assert resp.status_code == 404

    def test_contact_write_needs_the_owners_permission(self, client, db):
        """entities.write edits an entity's contact but not a person's."""
        _ensure_org_settings(db)
        admin = _create_user(db, suffix="ent-ct3")
        entity = client.post(
            "/api/v1/entities/", json=_entity_payload(name="Permisos SL ent-ct3"),
            cookies=_auth_cookie(admin),
        ).json()

        person = Person(first_name="Luis", last_name="Mora ent-ct3")
        db.add(person)
        db.flush()
        person_contact = Contact(party_id=person.party_id, value="600000003")
        entity_contact = Contact(party_id=entity["id"], value="900000003")
        db.add_all([person_contact, entity_contact])
        db.flush()

        staff = _user_with(db, {"entities.read", "entities.write"}, slug="ent-only-ct3")
        cookies = _auth_cookie(staff)

        resp = client.put(
            f"/api/v1/contacts/{entity_contact.id}", json={"label": "Mío"},
            cookies=cookies,
        )
        assert resp.status_code == 200

        resp = client.put(
            f"/api/v1/contacts/{person_contact.id}", json={"label": "Ajeno"},
            cookies=cookies,
        )
        assert resp.status_code == 403


class TestPartySearch:
    def test_finds_people_and_entities_but_not_the_club(self, client, db):
        org = _ensure_org_settings(db)
        admin = _create_user(db, suffix="ent-s1")
        cookies = _auth_cookie(admin)
        entity = client.post(
            "/api/v1/entities/",
            json=_entity_payload(name="Patronal Zeta ent-s1", national_id="Gs1"),
            cookies=cookies,
        ).json()
        person = Person(first_name="Zacarías", last_name="Zeta ent-s1")
        db.add(person)
        db.flush()

        resp = client.get("/api/v1/parties/search?q=Zeta ent-s1", cookies=cookies)
        assert resp.status_code == 200
        results = resp.json()
        ids = {r["id"] for r in results}
        assert entity["id"] in ids
        assert person.party_id in ids
        assert org.party_id not in ids
        kinds = {r["id"]: r["kind"] for r in results}
        assert kinds[entity["id"]] == "company"
        assert kinds[person.party_id] == "person"

    def test_billing_only_role_may_search(self, client, db):
        _ensure_org_settings(db)
        user = _user_with(db, {"billing.read", "billing.write"}, slug="billing-only-s2")
        resp = client.get("/api/v1/parties/search?q=nadie", cookies=_auth_cookie(user))
        assert resp.status_code == 200

    def test_member_role_may_not_search(self, client, db):
        member_user = _create_user(db, role="member", suffix="ent-s3")
        resp = client.get(
            "/api/v1/parties/search?q=algo", cookies=_auth_cookie(member_user)
        )
        assert resp.status_code == 403
