"""Emptied fields are cleared on save (#283); blank names are refused (#285)."""

import pytest

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.members.models import Group, Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


def _admin(db):
    person = Person(first_name="Admin", last_name="Clear", email="admin-clear@examplee6e3b1.com")
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id, email="admin-clear@examplee6e3b1.com",
        password_hash=hash_password("password123"), role="admin", is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _cookie(user):
    return {"access_token": create_access_token(user.id)}


@pytest.fixture
def admin(client, db):
    user = _admin(db)
    client.cookies.update(_cookie(user))
    return user


def _member_without_login(client):
    response = client.post(
        "/api/v1/members/",
        json={
            "first_name": "Aina",
            "last_name": "Torrent",
            "email": "aina-clear@examplee6e3b1.com",
            "date_of_birth": "1990-05-12",
            "national_id": "12345678Z",
            "internal_notes": "Pays in cash",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


class TestClearingMemberFields:
    def test_null_clears_every_optional_field(self, client, db, admin):
        member_id = _member_without_login(client)

        response = client.put(
            f"/api/v1/members/{member_id}",
            json={
                "first_name": "Aina",
                "last_name": "Torrent",
                "email": None,
                "date_of_birth": None,
                "gender": None,
                "national_id": None,
                "internal_notes": None,
            },
        )

        assert response.status_code == 200, response.text
        member = db.query(Member).filter(Member.id == member_id).one()
        db.refresh(member.person)
        db.refresh(member)
        assert member.person.email is None
        assert member.person.date_of_birth is None
        assert member.person.national_id is None
        assert member.internal_notes is None

    def test_a_member_with_a_login_keeps_an_email(self, client, db, admin):
        response = client.put(
            f"/api/v1/members/{self._member_with_login(db).id}",
            json={"email": None},
        )

        assert response.status_code == 400

    @staticmethod
    def _member_with_login(db):
        person = Person(first_name="Log", last_name="In", email="login-clear@examplee6e3b1.com")
        db.add(person)
        db.flush()
        user = User(
            person_id=person.id, email=person.email,
            password_hash=hash_password("password123"), role="member", is_active=True,
        )
        db.add(user)
        db.flush()
        member = Member(person_id=person.id, user_id=user.id, status="active")
        db.add(member)
        db.flush()
        return member


class TestClearingMembershipTypeGroup:
    def test_null_removes_the_group(self, client, db, admin):
        group = Group(name="Honorary", slug="honorary-clear", is_active=True)
        db.add(group)
        db.flush()
        mt = MembershipType(name="Honorary", slug="honorary-clear", group_id=group.id, is_active=True)
        db.add(mt)
        db.flush()

        response = client.put(f"/api/v1/membership-types/{mt.id}", json={"group_id": None})

        assert response.status_code == 200, response.text
        assert response.json()["group_id"] is None


BLANK = ["   ", "\t", " \n "]


class TestBlankNames:
    @pytest.mark.parametrize("blank", BLANK)
    @pytest.mark.parametrize("field", ["first_name", "last_name"])
    def test_member_create_refuses_a_blank_name(self, client, db, admin, field, blank):
        body = {"first_name": "Aina", "last_name": "Torrent", field: blank}

        assert client.post("/api/v1/members/", json=body).status_code == 422

    @pytest.mark.parametrize("value", ["   ", None])
    @pytest.mark.parametrize("field", ["first_name", "last_name"])
    def test_member_update_refuses_a_blank_or_null_name(self, client, db, admin, field, value):
        member_id = _member_without_login(client)

        response = client.put(f"/api/v1/members/{member_id}", json={field: value})

        assert response.status_code == 422
        person = db.query(Member).filter(Member.id == member_id).one().person
        db.refresh(person)
        assert (person.first_name, person.last_name) == ("Aina", "Torrent")

    def test_member_name_is_stored_trimmed(self, client, db, admin):
        response = client.post(
            "/api/v1/members/", json={"first_name": "  Aina ", "last_name": "\tTorrent  "}
        )

        assert response.status_code == 201
        assert response.json()["person"]["first_name"] == "Aina"
        assert response.json()["person"]["last_name"] == "Torrent"

    @pytest.mark.parametrize("field", ["first_name", "last_name"])
    def test_sign_up_refuses_a_blank_name(self, client, db, field):
        body = {
            "first_name": "New", "last_name": "User",
            "email": "blank-signup@examplee6e3b1.com", "password": "password123",
        }
        body[field] = "   "

        assert client.post("/api/v1/auth/register", json=body).status_code == 422


class TestBlankSpaceName:
    @pytest.fixture(autouse=True)
    def _bookings_on(self, db):
        org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
        if not org:
            org = OrganizationSettings(
                id=1, name="Club", locale="es", timezone="Europe/Madrid", currency="EUR",
            )
            db.add(org)
        org.features = {"bookings": True}
        db.flush()

    def _space(self, client, name="Court 1"):
        return client.post(
            "/api/v1/spaces",
            json={"name": name, "open_time": "08:00:00", "close_time": "22:00:00"},
        )

    @pytest.mark.parametrize("blank", BLANK)
    def test_create_refuses_a_blank_name(self, client, admin, blank):
        assert self._space(client, blank).status_code == 422

    @pytest.mark.parametrize("value", ["   ", None])
    def test_update_refuses_a_blank_or_null_name(self, client, admin, value):
        space_id = self._space(client).json()["id"]

        response = client.put(f"/api/v1/spaces/{space_id}", json={"name": value})

        assert response.status_code == 422

    def test_name_is_stored_trimmed(self, client, admin):
        assert self._space(client, "  Court 2 ").json()["name"] == "Court 2"
