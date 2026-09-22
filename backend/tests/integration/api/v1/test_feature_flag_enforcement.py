"""Server-side enforcement of the organization `features` flags.

The question these pin down is the one a hidden button cannot answer: with a flag
switched off, does the API *refuse*, or does only the interface stop offering it?
The frontend hides nav entries and tabs on these flags, and an interface that
merely hides is bypassed by typing the URL.

Five of the flags gate an API surface, and every route behind them carries its
guard. These tests hold that line — each asserts the refusal for one route of the
router, so a new route added without the guard is not caught here; what is caught
is a guard being removed from the route it protects.

`gender_options` is the exception and the reason this file has an xfail: the org
defines a closed list, the member forms render a select from it, and the API
accepts any string. See the tripwire at the bottom.
"""

import pytest

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import Role, User
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person

SUFFIX = "@example4f2a91.test"


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id)}


def _org(db, features: dict) -> OrganizationSettings:
    """Set the whole `features` map, creating the single settings row if absent."""
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
    org.features = features
    db.flush()
    return org


def _super_admin(db, email=f"flag-admin{SUFFIX}") -> User:
    """A super admin, so a refusal is never ambiguous with a missing permission."""
    person = Person(first_name="Flag", last_name="Admin", email=email)
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=email,
        password_hash=hash_password("password123"),
        is_active=True,
    )
    role = db.query(Role).filter(Role.slug == "super_admin").first()
    if role:
        user.roles.append(role)
    db.add(user)
    db.flush()
    return user


def _member(db, email=f"flag-member{SUFFIX}") -> Member:
    person = Person(first_name="Flag", last_name="Member", email=email)
    db.add(person)
    db.flush()
    mtype = db.query(MembershipType).first()
    member = Member(
        person_id=person.id,
        membership_type_id=mtype.id if mtype else None,
        status="active",
    )
    db.add(member)
    db.flush()
    return member


# One representative route per flag that gates an API surface. Each router's
# guard returns 404 rather than 403 — an off feature is absent, not forbidden,
# so the flag does not leak the existence of what it disables.
SURFACE_FLAGS = [
    pytest.param("bookings", "/api/v1/spaces", id="bookings"),
    pytest.param("communications", "/api/v1/announcements", id="communications"),
    pytest.param("custom_roles", "/api/v1/roles", id="custom_roles"),
    pytest.param("custom_profile_fields", "/api/v1/custom-fields/", id="custom_fields"),
    # The admin card route, not `/me/card`: a staff account has no member record
    # of its own, so `/me/card` would answer 404 for that reason and the refusal
    # test could not tell the guard from a missing member.
    pytest.param("member_card", "/api/v1/members/{member_id}/card", id="member_card"),
]


class TestSurfaceFlagsRefuseWhenOff:
    @pytest.mark.parametrize("flag,path", SURFACE_FLAGS)
    def test_route_404s_while_the_flag_is_off(self, client, db, flag, path):
        """Off means the API refuses, not merely that the nav entry is hidden."""
        _org(db, {})  # every flag absent, which reads as off
        admin = _super_admin(db)
        member = _member(db, email=f"flag-off-{flag}{SUFFIX}")
        client.cookies.update(_auth_cookie(admin))

        response = client.get(path.format(member_id=member.id))

        assert response.status_code == 404, (
            f"{path} answered {response.status_code} with `{flag}` off — a super "
            f"admin reached a disabled feature, so the flag only hides the button"
        )

    @pytest.mark.parametrize("flag,path", SURFACE_FLAGS)
    def test_route_is_reachable_while_the_flag_is_on(self, client, db, flag, path):
        """The mirror of the above: without it, a route broken for other reasons
        would satisfy the refusal test and the pair would prove nothing."""
        _org(db, {flag: True})
        admin = _super_admin(db)
        member = _member(db, email=f"flag-on-{flag}{SUFFIX}")
        client.cookies.update(_auth_cookie(admin))

        response = client.get(path.format(member_id=member.id))

        assert response.status_code != 404, (
            f"{path} 404s with `{flag}` on, so the refusal test above cannot "
            f"distinguish the guard from a route that never works"
        )


class TestGenderOptionsAreServerEnforced:
    """`gender_options` is the one flag of the 21 with no backend read at all.

    The org stores a closed list of `{value, label_es, label_ca, label_en}`; the
    member form and the profile form both render a select from it. The API takes
    `gender: str | None = Field(max_length=20)` and validates nothing, so any
    string within the length limit is stored. A value outside the list then has
    no label in any locale and renders blank wherever it is shown.
    """

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "No server-side validation of `gender` against `features.gender_options`. "
            "Remove this marker and invert nothing once the schema validates the "
            "value — the assertion below is already the desired behaviour."
        ),
    )
    def test_gender_outside_the_configured_options_is_refused(self, client, db):
        _org(
            db,
            {
                "gender_options": [
                    {
                        "value": "female",
                        "label_es": "Mujer",
                        "label_ca": "Dona",
                        "label_en": "Female",
                    }
                ]
            },
        )
        admin = _super_admin(db)
        member = _member(db)
        client.cookies.update(_auth_cookie(admin))

        response = client.put(
            f"/api/v1/members/{member.id}",
            json={"gender": "not-an-option"},
        )

        assert response.status_code == 422, (
            "the API stored a gender the organization does not offer; the select "
            "in the UI is the only thing constraining it"
        )

    def test_a_configured_gender_is_accepted(self, client, db):
        """The control: the refusal above must be about the list, not the field."""
        _org(
            db,
            {
                "gender_options": [
                    {
                        "value": "female",
                        "label_es": "Mujer",
                        "label_ca": "Dona",
                        "label_en": "Female",
                    }
                ]
            },
        )
        admin = _super_admin(db)
        member = _member(db, email=f"flag-member-ok{SUFFIX}")
        client.cookies.update(_auth_cookie(admin))

        response = client.put(
            f"/api/v1/members/{member.id}",
            json={"gender": "female"},
        )

        assert response.status_code == 200
        assert response.json()["person"]["gender"] == "female"
