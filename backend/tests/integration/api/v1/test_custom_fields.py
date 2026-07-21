"""Integration tests for custom profile fields — definitions and values."""

from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.custom_fields.models import CustomFieldDefinition
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


def _auth_cookie(user):
    from app.core.security.jwt import create_access_token

    return {"access_token": create_access_token(user.id, user.role)}


def _ensure_org(db, *, enabled=True):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(
            id=1,
            name="Test Club",
            locale="es",
            timezone="Europe/Madrid",
            currency="EUR",
            date_format="DD/MM/YYYY",
            brand_color="#0083ad",
        )
        db.add(org)
    org.features = {"custom_profile_fields": True} if enabled else {}
    db.flush()
    return org


def _create_user(db, role="admin", email=None):
    email = email or f"{role}-cf@test.com"
    person = Person(first_name=role.title(), last_name="Tester", email=email)
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=email,
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _definition(db, **kwargs):
    defaults = dict(
        key="shirt_size",
        field_type="text",
        label="Shirt size",
        labels={},
        required=False,
        member_access="read",
        admin_access="write",
        sort_order=0,
        active=True,
    )
    defaults.update(kwargs)
    definition = CustomFieldDefinition(**defaults)
    db.add(definition)
    db.flush()
    return definition


class TestFeatureGate:
    def test_definitions_404_when_disabled(self, client, db):
        _ensure_org(db, enabled=False)
        user = _create_user(db, "super_admin")
        response = client.get("/api/v1/custom-fields/", cookies=_auth_cookie(user))
        assert response.status_code == 404

    def test_values_404_when_disabled(self, client, db):
        _ensure_org(db, enabled=False)
        user = _create_user(db, "super_admin")
        response = client.get(
            f"/api/v1/persons/{user.person_id}/custom-fields/",
            cookies=_auth_cookie(user),
        )
        assert response.status_code == 404


class TestDefinitions:
    def test_super_admin_creates_a_definition(self, client, db):
        _ensure_org(db)
        user = _create_user(db, "super_admin")
        response = client.post(
            "/api/v1/custom-fields/",
            json={"key": "licence_no", "field_type": "text", "label": "Licence"},
            cookies=_auth_cookie(user),
        )
        assert response.status_code == 201
        body = response.json()
        assert body["key"] == "licence_no"
        # Documented defaults.
        assert body["member_access"] == "read"
        assert body["admin_access"] == "write"

    def test_admin_cannot_create_a_definition(self, client, db):
        _ensure_org(db)
        user = _create_user(db, "admin")
        response = client.post(
            "/api/v1/custom-fields/",
            json={"key": "licence_no", "field_type": "text", "label": "Licence"},
            cookies=_auth_cookie(user),
        )
        assert response.status_code == 403

    def test_duplicate_key_is_rejected(self, client, db):
        _ensure_org(db)
        _definition(db, key="shirt_size")
        user = _create_user(db, "super_admin")
        response = client.post(
            "/api/v1/custom-fields/",
            json={"key": "shirt_size", "field_type": "text", "label": "Dup"},
            cookies=_auth_cookie(user),
        )
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["body", "key"]

    def test_select_requires_options(self, client, db):
        _ensure_org(db)
        user = _create_user(db, "super_admin")
        response = client.post(
            "/api/v1/custom-fields/",
            json={"key": "size", "field_type": "select", "label": "Size"},
            cookies=_auth_cookie(user),
        )
        assert response.status_code == 422

    def test_key_and_field_type_are_immutable(self, client, db):
        _ensure_org(db)
        definition = _definition(db, key="shirt_size", field_type="text")
        user = _create_user(db, "super_admin")
        response = client.patch(
            f"/api/v1/custom-fields/{definition.id}",
            json={"key": "renamed", "field_type": "number", "label": "New label"},
            cookies=_auth_cookie(user),
        )
        assert response.status_code == 200
        db.refresh(definition)
        assert definition.key == "shirt_size"
        assert definition.field_type == "text"
        assert definition.label == "New label"

    def test_member_does_not_see_a_hidden_definition(self, client, db):
        _ensure_org(db)
        _definition(db, key="visible", member_access="read")
        _definition(db, key="internal", member_access="hidden")
        member = _create_user(db, "member")

        keys = [
            d["key"]
            for d in client.get(
                "/api/v1/custom-fields/", cookies=_auth_cookie(member)
            ).json()
        ]
        assert keys == ["visible"]

    def test_admin_sees_hidden_definitions_with_writable_flag(self, client, db):
        _ensure_org(db)
        _definition(db, key="internal", member_access="hidden", admin_access="read")
        admin = _create_user(db, "admin")

        body = client.get(
            "/api/v1/custom-fields/", cookies=_auth_cookie(admin)
        ).json()
        assert body[0]["key"] == "internal"
        assert body[0]["writable"] is False

    def test_delete_archives_a_definition_that_holds_values(self, client, db):
        _ensure_org(db)
        definition = _definition(db, key="shirt_size", admin_access="write")
        admin = _create_user(db, "admin")
        target = _create_user(db, "member", email="target-archive@test.com")
        client.put(
            f"/api/v1/persons/{target.person_id}/custom-fields/",
            json={"shirt_size": "M"},
            cookies=_auth_cookie(admin),
        )

        superuser = _create_user(db, "super_admin")
        response = client.delete(
            f"/api/v1/custom-fields/{definition.id}", cookies=_auth_cookie(superuser)
        )
        assert response.status_code == 204
        db.refresh(definition)
        assert definition.active is False

    def test_delete_removes_an_unused_definition(self, client, db):
        _ensure_org(db)
        definition = _definition(db, key="unused")
        superuser = _create_user(db, "super_admin")
        response = client.delete(
            f"/api/v1/custom-fields/{definition.id}", cookies=_auth_cookie(superuser)
        )
        assert response.status_code == 204
        assert (
            db.query(CustomFieldDefinition)
            .filter(CustomFieldDefinition.id == definition.id)
            .first()
            is None
        )


class TestValues:
    def test_round_trip_set_update_and_clear(self, client, db):
        _ensure_org(db)
        _definition(db, key="shirt_size")
        admin = _create_user(db, "admin")
        target = _create_user(db, "member", email="target-round@test.com")
        url = f"/api/v1/persons/{target.person_id}/custom-fields/"
        cookies = _auth_cookie(admin)

        assert client.get(url, cookies=cookies).json() == {"shirt_size": None}

        assert client.put(url, json={"shirt_size": "M"}, cookies=cookies).json() == {
            "shirt_size": "M"
        }
        assert client.put(url, json={"shirt_size": "L"}, cookies=cookies).json() == {
            "shirt_size": "L"
        }
        # An omitted key clears the field — whole-map semantics.
        assert client.put(url, json={}, cookies=cookies).json() == {"shirt_size": None}

    def test_values_are_coerced_and_validated(self, client, db):
        _ensure_org(db)
        _definition(db, key="joined_on", field_type="date")
        admin = _create_user(db, "admin")
        target = _create_user(db, "member", email="target-coerce@test.com")
        url = f"/api/v1/persons/{target.person_id}/custom-fields/"
        cookies = _auth_cookie(admin)

        assert client.put(
            url, json={"joined_on": "2026-07-21"}, cookies=cookies
        ).json() == {"joined_on": "2026-07-21"}

        bad = client.put(url, json={"joined_on": "21/07/2026"}, cookies=cookies)
        assert bad.status_code == 422
        assert bad.json()["detail"][0]["loc"] == ["body", "joined_on"]

    def test_select_rejects_an_undefined_option(self, client, db):
        _ensure_org(db)
        _definition(
            db,
            key="size",
            field_type="select",
            options=[{"value": "s", "label": "S"}],
        )
        admin = _create_user(db, "admin")
        target = _create_user(db, "member", email="target-select@test.com")

        response = client.put(
            f"/api/v1/persons/{target.person_id}/custom-fields/",
            json={"size": "xl"},
            cookies=_auth_cookie(admin),
        )
        assert response.status_code == 422

    def test_required_field_blocks_the_save(self, client, db):
        _ensure_org(db)
        _definition(db, key="licence_no", required=True)
        admin = _create_user(db, "admin")
        target = _create_user(db, "member", email="target-required@test.com")

        response = client.put(
            f"/api/v1/persons/{target.person_id}/custom-fields/",
            json={},
            cookies=_auth_cookie(admin),
        )
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["body", "licence_no"]

    def test_unknown_key_is_rejected(self, client, db):
        _ensure_org(db)
        admin = _create_user(db, "admin")
        target = _create_user(db, "member", email="target-unknown@test.com")

        response = client.put(
            f"/api/v1/persons/{target.person_id}/custom-fields/",
            json={"nope": "x"},
            cookies=_auth_cookie(admin),
        )
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["body", "nope"]

    def test_inactive_definition_is_ignored_not_rejected(self, client, db):
        _ensure_org(db)
        _definition(db, key="retired", active=False)
        admin = _create_user(db, "admin")
        target = _create_user(db, "member", email="target-inactive@test.com")

        response = client.put(
            f"/api/v1/persons/{target.person_id}/custom-fields/",
            json={"retired": "x"},
            cookies=_auth_cookie(admin),
        )
        assert response.status_code == 200
        assert "retired" not in response.json()

    def test_admin_cannot_write_a_read_only_field(self, client, db):
        _ensure_org(db)
        _definition(db, key="locked", admin_access="read")
        admin = _create_user(db, "admin")
        target = _create_user(db, "member", email="target-locked@test.com")

        response = client.put(
            f"/api/v1/persons/{target.person_id}/custom-fields/",
            json={"locked": "x"},
            cookies=_auth_cookie(admin),
        )
        assert response.status_code == 422
        assert response.json()["detail"][0]["msg"] == "This field is not editable"

    def test_member_cannot_reach_another_persons_values(self, client, db):
        _ensure_org(db)
        _definition(db, key="shirt_size")
        member = _create_user(db, "member", email="nosy@test.com")
        other = _create_user(db, "member", email="other@test.com")

        response = client.get(
            f"/api/v1/persons/{other.person_id}/custom-fields/",
            cookies=_auth_cookie(member),
        )
        assert response.status_code == 403

    def test_unknown_person_is_404(self, client, db):
        _ensure_org(db)
        admin = _create_user(db, "admin")
        response = client.get(
            "/api/v1/persons/999999/custom-fields/", cookies=_auth_cookie(admin)
        )
        assert response.status_code == 404


class TestSelfService:
    def test_member_reads_and_writes_own_values(self, client, db):
        _ensure_org(db)
        _definition(db, key="shirt_size", member_access="write")
        member = _create_user(db, "member", email="self-write@test.com")
        cookies = _auth_cookie(member)

        assert client.get("/api/v1/me/custom-fields/", cookies=cookies).json() == {
            "shirt_size": None
        }
        assert client.put(
            "/api/v1/me/custom-fields/", json={"shirt_size": "M"}, cookies=cookies
        ).json() == {"shirt_size": "M"}

    def test_member_cannot_write_a_read_only_field(self, client, db):
        _ensure_org(db)
        _definition(db, key="category", member_access="read")
        member = _create_user(db, "member", email="self-read@test.com")

        response = client.put(
            "/api/v1/me/custom-fields/",
            json={"category": "senior"},
            cookies=_auth_cookie(member),
        )
        assert response.status_code == 422

    def test_hidden_field_is_unknown_to_a_member(self, client, db):
        _ensure_org(db)
        _definition(db, key="internal", member_access="hidden")
        member = _create_user(db, "member", email="self-hidden@test.com")
        cookies = _auth_cookie(member)

        assert "internal" not in client.get(
            "/api/v1/me/custom-fields/", cookies=cookies
        ).json()
        # Probing a guessed key must not confirm the field exists.
        response = client.put(
            "/api/v1/me/custom-fields/", json={"internal": "x"}, cookies=cookies
        )
        assert response.status_code == 422
        assert response.json()["detail"][0]["msg"] == "Unknown field"

    def test_member_save_preserves_admin_only_fields(self, client, db):
        """A member saving their form must not wipe fields they can't write."""
        _ensure_org(db)
        _definition(db, key="shirt_size", member_access="write")
        _definition(db, key="category", member_access="read", admin_access="write")
        admin = _create_user(db, "admin")
        member = _create_user(db, "member", email="preserve@test.com")

        client.put(
            f"/api/v1/persons/{member.person_id}/custom-fields/",
            json={"category": "senior", "shirt_size": "S"},
            cookies=_auth_cookie(admin),
        )
        body = client.put(
            "/api/v1/me/custom-fields/",
            json={"shirt_size": "M"},
            cookies=_auth_cookie(member),
        ).json()

        assert body == {"shirt_size": "M", "category": "senior"}

    def test_required_admin_only_field_does_not_block_a_member(self, client, db):
        """required is enforced only over what the actor can actually write."""
        _ensure_org(db)
        _definition(db, key="shirt_size", member_access="write")
        _definition(
            db, key="licence_no", member_access="read", admin_access="write", required=True
        )
        member = _create_user(db, "member", email="required-admin@test.com")

        response = client.put(
            "/api/v1/me/custom-fields/",
            json={"shirt_size": "M"},
            cookies=_auth_cookie(member),
        )
        assert response.status_code == 200
