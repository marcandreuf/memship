"""A custom staff role built from administrative read keys cannot read.

The three xfails below are memship#244. They are ``strict`` on purpose: when the
bug is fixed they start passing, the suite goes red, and whoever fixed it is
told to delete the marker. A non-strict xfail would let the fix land silently
and the test rot into noise.

`activities.read` gates exactly one route in the whole API (discount codes).
The activity list and detail, membership types, groups, contacts and custom
fields are all gated on `self.*` keys instead. The built-in `admin` role hides
this because ADMIN_SEED_KEYS is the whole catalogue minus reserved, self keys
included — so only a *custom* role is affected, which is the whole point of
the custom-roles feature.
"""

import pytest

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import Role, RolePermission, User, UserRoleAssignment
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id)}


def _org(db):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(
            id=1, name="Test Club", locale="es", timezone="Europe/Madrid",
            currency="EUR", date_format="DD/MM/YYYY", brand_color="#0083ad",
        )
        db.add(org)
    org.features = {"custom_roles": True}
    db.flush()
    return org


def _staff_with(db, keys, *, slug):
    """A user holding exactly one custom role granting exactly `keys`."""
    role = Role(slug=slug, name=slug.title(), is_system=False)
    db.add(role)
    db.flush()
    for key in sorted(keys):
        db.add(RolePermission(role_id=role.id, permission_key=key))
    email = f"{slug}@examplea91c22.com"
    person = Person(first_name="Custom", last_name="Staff", email=email)
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id, email=email,
        password_hash=hash_password("password123"), is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(UserRoleAssignment(user_id=user.id, role_id=role.id))
    db.flush()
    return user


class TestActivitiesManagerRole:
    def test_can_write_activities(self, client, db):
        _org(db)
        user = _staff_with(
            db, {"activities.read", "activities.write", "activities.publish"},
            slug="activities-manager-w",
        )
        r = client.post(
            "/api/v1/activities/",
            json={"name": "Yoga", "start_date": "2026-10-01", "end_date": "2026-10-31"},
            cookies=_auth_cookie(user),
        )
        assert r.status_code in (200, 201, 422), r.text

    @pytest.mark.xfail(
        strict=True, reason="memship#244 — activities.read holder is refused, asked for self.activities.read"
    )
    def test_cannot_list_activities(self, client, db):
        _org(db)
        user = _staff_with(
            db, {"activities.read", "activities.write", "activities.publish"},
            slug="activities-manager-r",
        )
        r = client.get("/api/v1/activities/", cookies=_auth_cookie(user))
        assert r.status_code == 200, (
            f"activities.read holder got {r.status_code}: {r.text}"
        )


class TestMembershipManagerRole:
    @pytest.mark.xfail(
        strict=True, reason="memship#244 — membership.read gates no route at all"
    )
    def test_cannot_list_membership_types(self, client, db):
        _org(db)
        user = _staff_with(
            db, {"membership.read", "membership.write"}, slug="membership-manager",
        )
        r = client.get("/api/v1/membership-types/", cookies=_auth_cookie(user))
        assert r.status_code == 200, (
            f"membership.read holder got {r.status_code}: {r.text}"
        )


class TestMembersManagerRole:
    """The dual-audience pattern: the route declares the *self* key as its
    dependency so a member can reach it, then narrows in the body with
    `user_has(current_user, "members.read")`. A staff-only custom role never
    gets past the dependency."""

    def test_can_list_members(self, client, db):
        _org(db)
        user = _staff_with(db, {"members.read", "members.write"}, slug="members-manager-l")
        r = client.get("/api/v1/members/", cookies=_auth_cookie(user))
        assert r.status_code == 200, f"members.read holder got {r.status_code}: {r.text}"

    @pytest.mark.xfail(
        strict=True, reason="memship#244 — members.read holder is refused, asked for self.profile.read"
    )
    def test_cannot_open_a_member(self, client, db):
        _org(db)
        user = _staff_with(db, {"members.read", "members.write"}, slug="members-manager-d")
        r = client.get("/api/v1/members/1", cookies=_auth_cookie(user))
        assert r.status_code != 403, (
            f"members.read holder got 403 opening a member: {r.text}"
        )
