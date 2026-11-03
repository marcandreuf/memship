"""Server-side enforcement of the organization `features` flags.

The question these pin down is the one a hidden button cannot answer: with a flag
switched off, does the API *refuse*, or does only the interface stop offering it?
The frontend hides nav entries and tabs on these flags, and an interface that
merely hides is bypassed by typing the URL.

This file is the inventory of what the server enforces. Seven flags refuse
something, in three different shapes, and an eighth changes behaviour without
refusing anything at all. "Enforced server-side" therefore has no single meaning
across the set, which is why the shape is named per class rather than assumed.

**Module gates** hide a whole module that should not exist on this instance:
`bookings`, `communications`, `custom_profile_fields`, `custom_roles`,
`member_card`. They refuse with **404** rather than 403, so an off feature is
absent rather than forbidden and the flag does not leak the existence of what it
disables. Every route behind them carries its guard; each test below asserts the
refusal for one route of the router, so a new route added without the guard is
not caught here — what is caught is a guard being removed from the route it
protects.

**An action gate** refuses one action on an endpoint that exists on every
instance: `public_registration`. It refuses with **403**, and the difference from
the module gates is deliberate rather than an oversight. `POST /auth/register` is
a route on every install, so a 404 there would be false and indistinguishable
from a mistyped URL, which makes a self-hoster's diagnosis harder instead of
easier. The state is not secret either: the frontend reads the same flag to hide
the registration link.

**A closed list** is enforced per value rather than by gating a router:
`gender_options`. The org stores the options, the forms render a select from
them, and the API refuses anything outside it.

`registration_requires_approval` is the eighth and belongs to none of these. It
refuses nothing in either position: off means a self-registration is approved
inline instead of landing `pending`. Its assertions are behavioural and live in
`test_registration_flow.py` beside the rest of that flow —
`test_register_lands_in_pending_without_number_or_session` and
`test_register_activates_immediately_when_approval_not_required`. Named here
because a reader counting enforced flags from this file would otherwise miss that
it exists and conclude the flag is unenforced rather than non-gating.
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
        party_id=person.party_id,
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
    # The card is issued per membership type since #428 Part 2, off by default,
    # so this member needs a type that issues one — otherwise the `member_card`
    # row below would 404 for the per-type reason and its reachable-while-on
    # half would stop proving that the **flag** is a working module gate.
    #
    # Created rather than only opted in: this suite runs against a freshly
    # migrated database with no seed data, so there is no type to find.
    mtype = db.query(MembershipType).first()
    if mtype is None:
        mtype = MembershipType(
            name="Flag Tier", slug="flag-tier", is_active=True, issues_card=True
        )
        db.add(mtype)
        db.flush()
    else:
        mtype.issues_card = True
        db.flush()
    member = Member(
        party_id=person.party_id,
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


class TestPublicRegistrationIsAnActionGate:
    """`public_registration` refuses with 403, and that is not a module gate slip.

    The five above answer 404 because the module should look absent. This one
    cannot: `POST /auth/register` is a route on every install, so a 404 would be
    false and indistinguishable from a mistyped URL. 403 is the honest answer and
    the one a self-hoster can diagnose.

    `test_registration_flow.py` also covers the refusal, from the flow's side and
    including the message. The pair here exists because this file is the
    enforcement inventory: a reader asking which flags the server refuses on, and
    with what status, should find the answer without knowing that the other file
    is where registration lives.
    """

    #: Unverified, unapproved, and discarded by the rollback: the account this
    #: would create is never reached, only the status code is read.
    PAYLOAD = {
        "first_name": "Gate",
        "last_name": "Probe",
        "email": f"flag-register{SUFFIX}",
        "password": "password123",
    }

    def test_register_is_refused_with_403_while_the_flag_is_off(self, client, db):
        _org(db, {"public_registration": False})

        response = client.post("/api/v1/auth/register", json=self.PAYLOAD)

        assert response.status_code == 403, (
            f"register answered {response.status_code} with `public_registration` "
            f"off; the flag hides the link in the UI, so an unrefused POST means "
            f"anyone can still sign up on an instance that has closed sign-ups"
        )

    def test_register_is_not_refused_while_the_flag_is_on(self, client, db):
        """The mirror, asserting `!= 403` rather than `== 201` on purpose.

        Register has a second refusal in front of it: with no mail transport
        configured it answers 503, so that an account nobody can reach is never
        minted. Asserting the created status would tie this test to whether the
        suite happens to have mail configured, which is not what it is about.
        """
        _org(db, {"public_registration": True})

        response = client.post("/api/v1/auth/register", json=self.PAYLOAD)

        assert response.status_code != 403, (
            "register answered 403 with `public_registration` on, so the refusal "
            "test above cannot distinguish the gate from a route that never works"
        )


class TestGenderOptionsAreServerEnforced:
    """`gender_options` is enforced by the server, not only by the select.

    The org stores a closed list of `{value, label_es, label_ca, label_en}`; the
    member form and the profile form both render a select from it. A value
    outside the list has no label in any locale and renders blank wherever it is
    shown, so `require_offered_gender` in `domains/persons/gender.py` refuses it.
    These tests pin that refusal.
    """

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
            "the API accepted a gender the organization does not offer, leaving "
            "the select in the UI as the only thing constraining it"
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
