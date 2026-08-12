"""Integration tests for role authoring, assignment and the escalation guard."""

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.audit.models import AuditLog
from app.domains.auth.models import Role, User, UserRoleAssignment
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id)}


def _ensure_org(db, *, enabled=True):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(
            id=1, name="Test Club", locale="es", timezone="Europe/Madrid",
            currency="EUR", date_format="DD/MM/YYYY", brand_color="#0083ad",
        )
        db.add(org)
    org.features = {"custom_roles": True} if enabled else {}
    db.flush()
    return org


def _user(db, role="admin", email=None):
    email = email or f"{role}-roles-api@examplee6e3b1.com"
    person = Person(first_name=role.title(), last_name="Tester", email=email)
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id, email=email,
        password_hash=hash_password("password123"), role=role, is_active=True,
    )
    db.add(user)
    db.flush()
    return user


class TestFeatureFlag:
    def test_screens_404_when_the_flag_is_off(self, client, db):
        _ensure_org(db, enabled=False)
        admin = _user(db, "super_admin")

        r = client.get("/api/v1/roles", cookies=_auth_cookie(admin))

        assert r.status_code == 404


class TestPermissionCatalog:
    def test_lists_the_whole_catalog_with_i18n_keys(self, client, db):
        _ensure_org(db)
        admin = _user(db, "super_admin")

        r = client.get("/api/v1/permissions", cookies=_auth_cookie(admin))

        assert r.status_code == 200
        body = r.json()
        assert len(body) == 41
        entry = next(p for p in body if p["key"] == "billing.run")
        assert entry["label_key"] == "permissions.billing.run.label"
        assert entry["description_key"] == "permissions.billing.run.description"

    def test_an_admin_cannot_read_the_catalog_without_roles_read(self, client, db):
        _ensure_org(db)
        member = _user(db, "member", email="cat-member@examplee6e3b1.com")

        r = client.get("/api/v1/permissions", cookies=_auth_cookie(member))

        assert r.status_code == 403


class TestRoleAuthoring:
    def test_super_admin_creates_a_custom_role(self, client, db):
        _ensure_org(db)
        boss = _user(db, "super_admin")

        r = client.post(
            "/api/v1/roles",
            json={"name": "Tesorero", "permission_keys": ["billing.read", "billing.write"]},
            cookies=_auth_cookie(boss),
        )

        assert r.status_code == 201
        assert r.json()["slug"] == "tesorero"
        assert sorted(r.json()["permission_keys"]) == ["billing.read", "billing.write"]

    def test_an_admin_cannot_author_roles(self, client, db):
        _ensure_org(db)
        admin = _user(db, "admin")

        r = client.post(
            "/api/v1/roles", json={"name": "Nope"}, cookies=_auth_cookie(admin)
        )

        assert r.status_code == 403

    def test_a_reserved_key_is_refused_on_a_custom_role(self, client, db):
        _ensure_org(db)
        boss = _user(db, "super_admin")

        r = client.post(
            "/api/v1/roles",
            json={"name": "Sneaky", "permission_keys": ["roles.write"]},
            cookies=_auth_cookie(boss),
        )

        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "reserved_permissions"

    def test_an_unknown_key_is_refused(self, client, db):
        _ensure_org(db)
        boss = _user(db, "super_admin")

        r = client.post(
            "/api/v1/roles",
            json={"name": "Ghost", "permission_keys": ["billing.teleport"]},
            cookies=_auth_cookie(boss),
        )

        assert r.status_code == 422

    def test_a_colliding_slug_is_409_not_500(self, client, db):
        _ensure_org(db)
        boss = _user(db, "super_admin")
        client.post("/api/v1/roles", json={"name": "Tesorero"}, cookies=_auth_cookie(boss))

        r = client.post(
            "/api/v1/roles", json={"name": "  tesorero "}, cookies=_auth_cookie(boss)
        )

        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "role_slug_exists"

    def test_a_system_role_cannot_be_deleted(self, client, db):
        _ensure_org(db)
        boss = _user(db, "super_admin")
        admin_role = db.query(Role).filter_by(slug="admin").one()

        r = client.delete(f"/api/v1/roles/{admin_role.id}", cookies=_auth_cookie(boss))

        assert r.status_code == 403

    def test_deleting_a_role_in_use_reports_the_count(self, client, db):
        _ensure_org(db)
        boss = _user(db, "super_admin")
        created = client.post(
            "/api/v1/roles",
            json={"name": "Coordinador", "permission_keys": ["activities.read"]},
            cookies=_auth_cookie(boss),
        ).json()
        victim = _user(db, "member", email="coord@examplee6e3b1.com")
        db.add(UserRoleAssignment(user_id=victim.id, role_id=created["id"]))
        db.flush()

        r = client.delete(f"/api/v1/roles/{created['id']}", cookies=_auth_cookie(boss))

        assert r.status_code == 409
        assert r.json()["detail"]["assigned_user_count"] == 1


class TestEscalationGuard:
    def test_an_admin_cannot_grant_super_admin(self, client, db):
        """super_admin stores no permission rows, so a naive subset check would
        pass this trivially. It must be refused by an explicit rule."""
        _ensure_org(db)
        admin = _user(db, "admin")
        target = _user(db, "member", email="escalate-target@examplee6e3b1.com")
        super_role = db.query(Role).filter_by(slug="super_admin").one()

        r = client.put(
            f"/api/v1/users/{target.id}/roles",
            json={"role_ids": [super_role.id]},
            cookies=_auth_cookie(admin),
        )

        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "escalation_blocked"

    def test_an_admin_cannot_grant_permissions_it_does_not_hold(self, client, db):
        _ensure_org(db)
        boss = _user(db, "super_admin")
        privileged = client.post(
            "/api/v1/roles",
            json={"name": "Schema Editor",
                  "permission_keys": ["settings.custom_fields.write"]},
            cookies=_auth_cookie(boss),
        ).json()
        admin = _user(db, "admin", email="narrow-admin@examplee6e3b1.com")
        target = _user(db, "member", email="narrow-target@examplee6e3b1.com")

        r = client.put(
            f"/api/v1/users/{target.id}/roles",
            json={"role_ids": [privileged["id"]]},
            cookies=_auth_cookie(admin),
        )

        assert r.status_code == 403
        assert "settings.custom_fields.write" in r.json()["detail"]["keys"]

    def test_a_super_admin_can_grant_anything(self, client, db):
        _ensure_org(db)
        boss = _user(db, "super_admin")
        target = _user(db, "member", email="grantee@examplee6e3b1.com")
        admin_role = db.query(Role).filter_by(slug="admin").one()

        r = client.put(
            f"/api/v1/users/{target.id}/roles",
            json={"role_ids": [admin_role.id]},
            cookies=_auth_cookie(boss),
        )

        assert r.status_code == 200
        assert {x["slug"] for x in r.json()["roles"]} == {"admin", "member"}

    def test_assignable_flag_agrees_with_what_put_accepts(self, client, db):
        _ensure_org(db)
        admin = _user(db, "admin")

        listing = client.get("/api/v1/roles", cookies=_auth_cookie(admin)).json()
        by_slug = {r["slug"]: r for r in listing}

        assert by_slug["super_admin"]["assignable"] is False
        assert by_slug["member"]["assignable"] is True


class TestMemberPinAndEmptySet:
    def test_an_empty_role_set_is_rejected(self, client, db):
        _ensure_org(db)
        boss = _user(db, "super_admin")
        target = _user(db, "member", email="empty-set@examplee6e3b1.com")

        r = client.put(
            f"/api/v1/users/{target.id}/roles",
            json={"role_ids": []},
            cookies=_auth_cookie(boss),
        )

        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "roles_required"

    def test_member_is_re_added_when_the_payload_omits_it(self, client, db):
        _ensure_org(db)
        boss = _user(db, "super_admin")
        target = _user(db, "member", email="pin-omitted@examplee6e3b1.com")
        admin_role = db.query(Role).filter_by(slug="admin").one()

        r = client.put(
            f"/api/v1/users/{target.id}/roles",
            json={"role_ids": [admin_role.id]},
            cookies=_auth_cookie(boss),
        )

        assert r.status_code == 200
        assert "member" in {x["slug"] for x in r.json()["roles"]}

    def test_the_last_super_admin_cannot_be_demoted(self, client, db):
        _ensure_org(db)
        boss = _user(db, "super_admin")
        member_role = db.query(Role).filter_by(slug="member").one()

        r = client.put(
            f"/api/v1/users/{boss.id}/roles",
            json={"role_ids": [member_role.id]},
            cookies=_auth_cookie(boss),
        )

        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "last_super_admin"


class TestAuthMePayload:
    def test_me_carries_roles_and_permissions_and_no_role_string(self, client, db):
        _ensure_org(db)
        admin = _user(db, "admin", email="me-payload@examplee6e3b1.com")

        body = client.get("/api/v1/auth/me", cookies=_auth_cookie(admin)).json()

        assert "role" not in body
        assert {r["slug"] for r in body["roles"]} == {"admin", "member"}
        assert "members.write" in body["permissions"]
        assert "roles.write" not in body["permissions"]

    def test_a_super_admin_sees_the_whole_catalog(self, client, db):
        _ensure_org(db)
        boss = _user(db, "super_admin", email="me-super@examplee6e3b1.com")

        body = client.get("/api/v1/auth/me", cookies=_auth_cookie(boss)).json()

        assert len(body["permissions"]) == 41
        assert "roles.write" in body["permissions"]


class TestAuditTrail:
    def test_creating_a_role_records_the_granted_keys(self, client, db):
        _ensure_org(db)
        boss = _user(db, "super_admin", email="audit-create@examplee6e3b1.com")

        created = client.post(
            "/api/v1/roles",
            json={"name": "Auditable", "permission_keys": ["billing.read"]},
            cookies=_auth_cookie(boss),
        ).json()

        row = (
            db.query(AuditLog)
            .filter(AuditLog.table_name == "roles", AuditLog.record_id == created["id"])
            .one()
        )
        assert row.action == "create"
        assert row.user_id == boss.id
        assert row.changed_fields == ["+billing.read"]

    def test_editing_a_role_records_added_and_removed_keys(self, client, db):
        _ensure_org(db)
        boss = _user(db, "super_admin", email="audit-update@examplee6e3b1.com")
        created = client.post(
            "/api/v1/roles",
            json={"name": "Shifting", "permission_keys": ["billing.read"]},
            cookies=_auth_cookie(boss),
        ).json()

        client.put(
            f"/api/v1/roles/{created['id']}",
            json={"permission_keys": ["billing.write"]},
            cookies=_auth_cookie(boss),
        )

        row = (
            db.query(AuditLog)
            .filter(
                AuditLog.table_name == "roles",
                AuditLog.record_id == created["id"],
                AuditLog.action == "update",
            )
            .one()
        )
        assert sorted(row.changed_fields) == ["+billing.write", "-billing.read"]

    def test_assigning_roles_records_the_slug_delta(self, client, db):
        _ensure_org(db)
        boss = _user(db, "super_admin", email="audit-assign@examplee6e3b1.com")
        target = _user(db, "member", email="audit-target@examplee6e3b1.com")
        admin_role = db.query(Role).filter_by(slug="admin").one()

        client.put(
            f"/api/v1/users/{target.id}/roles",
            json={"role_ids": [admin_role.id]},
            cookies=_auth_cookie(boss),
        )

        row = (
            db.query(AuditLog)
            .filter(AuditLog.table_name == "user_roles", AuditLog.record_id == target.id)
            .one()
        )
        assert row.changed_fields == ["+admin"]
        assert row.user_id == boss.id

    def test_a_refused_assignment_records_nothing(self, client, db):
        _ensure_org(db)
        admin = _user(db, "admin", email="audit-refused@examplee6e3b1.com")
        target = _user(db, "member", email="audit-refused-target@examplee6e3b1.com")
        super_role = db.query(Role).filter_by(slug="super_admin").one()

        client.put(
            f"/api/v1/users/{target.id}/roles",
            json={"role_ids": [super_role.id]},
            cookies=_auth_cookie(admin),
        )

        rows = (
            db.query(AuditLog)
            .filter(AuditLog.table_name == "user_roles", AuditLog.record_id == target.id)
            .all()
        )
        assert rows == []
