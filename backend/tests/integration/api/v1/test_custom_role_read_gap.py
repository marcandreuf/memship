"""A custom staff role can read the things it administers.

This was memship#244. Routes serving both audiences declared the *self-service*
key as their dependency so a member could reach them, then narrowed inside the
body with ``user_has(current_user, "<admin>.read")``. A custom role built from
administrative keys never reached the narrowing — it was refused at the gate.
The built-in ``admin`` role hid it, because ADMIN_SEED_KEYS is the whole
catalogue minus reserved, self keys included, so only a *custom* role was
affected, which is the whole point of the custom-roles feature.

Those gates are now ``require_any_permission(<admin key>, <self key>)``: the
administrative key admits staff, the self key still admits members, and the
body narrows as before. The tests below hold both halves of that — a custom
staff role gets in, and the member audience did not lose anything.

Detail routes assert ``!= 403`` rather than ``== 200``: whether the row exists
is not what this file is about, and a 404 is proof the gate was passed.
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
    org.features = {"custom_roles": True, "bookings": True}
    db.flush()
    return org


def _user_with(db, keys, *, slug):
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
    KEYS = {"activities.read", "activities.write", "activities.publish"}

    def test_can_write_activities(self, client, db):
        _org(db)
        user = _user_with(db, self.KEYS, slug="activities-manager-w")
        r = client.post(
            "/api/v1/activities/",
            json={"name": "Yoga", "start_date": "2026-10-01", "end_date": "2026-10-31"},
            cookies=_auth_cookie(user),
        )
        assert r.status_code in (200, 201, 422), r.text

    def test_can_list_activities(self, client, db):
        _org(db)
        user = _user_with(db, self.KEYS, slug="activities-manager-r")
        r = client.get("/api/v1/activities/", cookies=_auth_cookie(user))
        assert r.status_code == 200, (
            f"activities.read holder got {r.status_code}: {r.text}"
        )

    def test_can_open_an_activity(self, client, db):
        _org(db)
        user = _user_with(db, self.KEYS, slug="activities-manager-d")
        r = client.get("/api/v1/activities/1", cookies=_auth_cookie(user))
        assert r.status_code != 403, r.text


class TestMembershipManagerRole:
    """`membership.read` gated no route in the entire API before this fix."""

    KEYS = {"membership.read", "membership.write"}

    def test_can_list_membership_types(self, client, db):
        _org(db)
        user = _user_with(db, self.KEYS, slug="membership-manager")
        r = client.get("/api/v1/membership-types/", cookies=_auth_cookie(user))
        assert r.status_code == 200, (
            f"membership.read holder got {r.status_code}: {r.text}"
        )

    def test_can_open_a_membership_type(self, client, db):
        _org(db)
        user = _user_with(db, self.KEYS, slug="membership-manager-d")
        r = client.get("/api/v1/membership-types/1", cookies=_auth_cookie(user))
        assert r.status_code != 403, r.text

    def test_can_list_groups(self, client, db):
        """Groups pair with `membership.read` because their writes are
        `membership.write`, not `members.write`."""
        _org(db)
        user = _user_with(db, self.KEYS, slug="membership-manager-g")
        r = client.get("/api/v1/groups/", cookies=_auth_cookie(user))
        assert r.status_code == 200, r.text


class TestMembersManagerRole:
    """The dual-audience pattern: the route declares the *self* key as its
    dependency so a member can reach it, then narrows in the body with
    `user_has(current_user, "members.read")`."""

    KEYS = {"members.read", "members.write"}

    def test_can_list_members(self, client, db):
        _org(db)
        user = _user_with(db, self.KEYS, slug="members-manager-l")
        r = client.get("/api/v1/members/", cookies=_auth_cookie(user))
        assert r.status_code == 200, f"members.read holder got {r.status_code}: {r.text}"

    def test_can_open_a_member(self, client, db):
        _org(db)
        user = _user_with(db, self.KEYS, slug="members-manager-d")
        r = client.get("/api/v1/members/1", cookies=_auth_cookie(user))
        assert r.status_code != 403, (
            f"members.read holder got 403 opening a member: {r.text}"
        )

    def test_can_open_a_person(self, client, db):
        _org(db)
        user = _user_with(db, self.KEYS, slug="members-manager-p")
        r = client.get("/api/v1/persons/1", cookies=_auth_cookie(user))
        assert r.status_code != 403, r.text

    def test_can_list_contact_types(self, client, db):
        _org(db)
        user = _user_with(db, self.KEYS, slug="members-manager-c")
        r = client.get("/api/v1/contact-types/", cookies=_auth_cookie(user))
        assert r.status_code == 200, r.text


class TestDestructiveDualAudienceRoutes:
    """Two cancel routes hand `is_admin` to their service and were still gated
    on the self key alone, so a bookings or registrations manager could not
    cancel on a member's behalf. Nonexistent ids are used deliberately: a 404
    proves the gate was passed, which is all this file asserts."""

    def test_bookings_manager_can_reach_cancel_booking(self, client, db):
        _org(db)
        user = _user_with(db, {"bookings.read", "bookings.write"}, slug="bookings-manager")
        r = client.delete("/api/v1/bookings/999999", cookies=_auth_cookie(user))
        assert r.status_code != 403, r.text

    def test_registrations_manager_can_reach_cancel_registration(self, client, db):
        _org(db)
        user = _user_with(
            db, {"registrations.read", "registrations.write"}, slug="registrations-manager"
        )
        r = client.delete("/api/v1/registrations/999999", cookies=_auth_cookie(user))
        assert r.status_code != 403, r.text


class TestSessionIdentity:
    """`GET /auth/me` returns session identity — email, roles, resolved
    permissions — which every authenticated user needs to bootstrap the UI. It
    was gated on `self.profile.read`, so a custom staff role was refused and
    could not log in at all. It now takes `get_current_user` and no permission
    key, and tolerates a user with no member record."""

    @pytest.mark.parametrize(
        "keys,slug",
        [
            ({"members.read"}, "identity-members"),
            ({"billing.read"}, "identity-billing"),
            ({"bookings.read"}, "identity-bookings"),
        ],
    )
    def test_any_staff_role_can_read_its_own_session(self, client, db, keys, slug):
        _org(db)
        user = _user_with(db, keys, slug=slug)
        r = client.get("/api/v1/auth/me", cookies=_auth_cookie(user))
        assert r.status_code == 200, f"{sorted(keys)} holder got {r.text}"
        assert r.json()["member_id"] is None


class TestMemberAudienceUnchanged:
    """The self keys stayed on every gate, so the member audience is untouched.
    A regression here would mean the fix traded one audience for the other."""

    @pytest.mark.parametrize(
        "path,keys",
        [
            ("/api/v1/activities/", {"self.activities.read"}),
            ("/api/v1/membership-types/", {"self.activities.read"}),
            ("/api/v1/groups/", {"self.activities.read"}),
        ],
    )
    def test_member_can_still_read(self, client, db, path, keys):
        _org(db)
        slug = "member-" + path.strip("/").replace("/", "-")
        user = _user_with(db, keys, slug=slug)
        r = client.get(path, cookies=_auth_cookie(user))
        assert r.status_code == 200, f"member got {r.status_code} on {path}: {r.text}"

    def test_member_cannot_list_the_whole_club(self, client, db):
        """`GET /members/` is staff-only and was never dual-audience. Pinned
        here so the sweep above is not read as licence to widen it."""
        _org(db)
        user = _user_with(db, {"self.profile.read"}, slug="member-roster")
        r = client.get("/api/v1/members/", cookies=_auth_cookie(user))
        assert r.status_code == 403, r.text

    def test_member_can_read_its_own_session(self, client, db):
        _org(db)
        user = _user_with(db, {"self.profile.read"}, slug="member-identity")
        r = client.get("/api/v1/auth/me", cookies=_auth_cookie(user))
        assert r.status_code == 200, r.text
