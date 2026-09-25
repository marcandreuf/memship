"""A member's gender is checked against ``features.gender_options`` (#280)."""

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


def _org(db, *values):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(
            id=1, name="Test Club", locale="es", timezone="Europe/Madrid",
            currency="EUR", date_format="DD/MM/YYYY",
        )
        db.add(org)
    org.features = {
        "gender_options": [
            {"value": v, "label_es": v, "label_ca": v, "label_en": v} for v in values
        ]
    }
    db.flush()


def _user(db, role, email):
    person = Person(first_name=role.title(), last_name="Gender", email=email)
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id, email=email,
        password_hash=hash_password("password123"), role=role, is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _member(db, user, gender=None):
    mt = db.query(MembershipType).first()
    if not mt:
        mt = MembershipType(name="General", slug="general", is_active=True)
        db.add(mt)
        db.flush()
    user.person.gender = gender
    member = Member(
        person_id=user.person_id, user_id=user.id, membership_type_id=mt.id,
        member_number=f"G-{user.id:04d}", status="active",
    )
    db.add(member)
    db.flush()
    return member


def _login(client, user):
    client.cookies.update({"access_token": create_access_token(user.id)})


class TestMemberWrites:
    def test_create_refuses_a_value_not_offered(self, client, db):
        _org(db, "female")
        _login(client, _user(db, "admin", "admin-g@examplee6e3b1.com"))

        r = client.post("/api/v1/members/", json={
            "first_name": "A", "last_name": "B", "gender": "not-an-option",
        })

        assert r.status_code == 422

    def test_create_accepts_an_offered_value(self, client, db):
        _org(db, "female")
        _login(client, _user(db, "admin", "admin-g@examplee6e3b1.com"))

        r = client.post("/api/v1/members/", json={
            "first_name": "A", "last_name": "B", "gender": "female",
        })

        assert r.status_code == 201
        assert r.json()["person"]["gender"] == "female"

    def test_update_refuses_a_value_not_offered(self, client, db):
        _org(db, "female")
        member = _member(db, _user(db, "member", "m-g@examplee6e3b1.com"))
        _login(client, _user(db, "admin", "admin-g@examplee6e3b1.com"))

        r = client.put(f"/api/v1/members/{member.id}", json={"gender": "not-an-option"})

        assert r.status_code == 422
        db.refresh(member.person)
        assert member.person.gender is None

    def test_update_can_clear_it(self, client, db):
        _org(db, "female")
        member = _member(db, _user(db, "member", "m-g@examplee6e3b1.com"), gender="female")
        _login(client, _user(db, "admin", "admin-g@examplee6e3b1.com"))

        r = client.put(f"/api/v1/members/{member.id}", json={"gender": None})

        assert r.status_code == 200
        assert r.json()["person"]["gender"] is None

    def test_a_withdrawn_value_does_not_lock_the_record(self, client, db):
        # Stored while it was offered; the edit form sends it back unchanged.
        _org(db, "female")
        member = _member(db, _user(db, "member", "m-g@examplee6e3b1.com"), gender="male")
        _login(client, _user(db, "admin", "admin-g@examplee6e3b1.com"))

        read = client.get(f"/api/v1/members/{member.id}")
        r = client.put(f"/api/v1/members/{member.id}", json={
            "first_name": "Renamed", "gender": "male",
        })

        assert read.status_code == 200
        assert r.status_code == 200
        assert r.json()["person"]["gender"] == "male"

    def test_person_update_refuses_a_value_not_offered(self, client, db):
        _org(db, "female")
        member = _member(db, _user(db, "member", "m-g@examplee6e3b1.com"))
        _login(client, _user(db, "admin", "admin-g@examplee6e3b1.com"))

        r = client.put(f"/api/v1/persons/{member.person_id}", json={"gender": "not-an-option"})

        assert r.status_code == 422


class TestProfile:
    def test_refuses_a_value_not_offered(self, client, db):
        _org(db, "female")
        user = _user(db, "member", "m-g@examplee6e3b1.com")
        _member(db, user)
        _login(client, user)

        r = client.put("/api/v1/members/me/profile", json={"gender": "not-an-option"})

        assert r.status_code == 422

    def test_accepts_an_offered_value(self, client, db):
        _org(db, "female")
        user = _user(db, "member", "m-g@examplee6e3b1.com")
        _member(db, user)
        _login(client, user)

        r = client.put("/api/v1/members/me/profile", json={"gender": "female"})

        assert r.status_code == 200
        assert r.json()["gender"] == "female"
