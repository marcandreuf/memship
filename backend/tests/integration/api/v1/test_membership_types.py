"""Integration tests for membership type endpoints."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.members.models import MembershipType
from app.domains.persons.models import Person


def _create_user(db, role="admin"):
    person = Person(first_name="Admin", last_name="User", email=f"{role}@examplee6e3b1.com")
    db.add(person)
    db.flush()
    user = User(
        party_id=person.party_id,
        email=f"{role}@examplee6e3b1.com",
        password_hash=hash_password("password123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _auth_cookie(user):
    token = create_access_token(user.id)
    return {"access_token": token}


class TestMembershipTypeCRUD:
    def test_create_membership_type(self, client, db):
        user = _create_user(db, "admin")
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            "/api/v1/membership-types/",
            json={
                "name": "Premium",
                "slug": "premium",
                "description": "Premium membership",
                "base_price": 50.0,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Premium"
        assert data["slug"] == "premium"
        assert data["base_price"] == 50.0

    def test_list_membership_types(self, client, db):
        user = _create_user(db, "member")
        db.add(MembershipType(name="Basic", slug="basic", is_active=True))
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.get("/api/v1/membership-types/")
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_list_carries_the_age_band_and_default_flag(self, client, db):
        """The approval dropdown warns about age in the browser, so the list has
        to hand it the band and tell it which tier to pre-select."""
        user = _create_user(db, "member")
        db.add(
            MembershipType(
                name="Youth",
                slug="youth",
                max_age=15,
                min_age=6,
                is_active=True,
            )
        )
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.get("/api/v1/membership-types/")

        assert response.status_code == 200
        youth = next(mt for mt in response.json() if mt["slug"] == "youth")
        assert youth["min_age"] == 6
        assert youth["max_age"] == 15
        assert youth["is_default"] is False

    def test_update_membership_type(self, client, db):
        user = _create_user(db, "admin")
        mt = MembershipType(name="Old", slug="old", is_active=True)
        db.add(mt)
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            f"/api/v1/membership-types/{mt.id}",
            json={"name": "Updated"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated"

    def test_delete_membership_type(self, client, db):
        user = _create_user(db, "admin")
        mt = MembershipType(name="ToDelete", slug="to-delete", is_active=True)
        db.add(mt)
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.delete(f"/api/v1/membership-types/{mt.id}")
        assert response.status_code == 204

    def test_member_cannot_create(self, client, db):
        user = _create_user(db, "member")
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            "/api/v1/membership-types/",
            json={"name": "Blocked", "slug": "blocked"},
        )
        assert response.status_code == 403

    def test_duplicate_slug(self, client, db):
        user = _create_user(db, "admin")
        db.add(MembershipType(name="Existing", slug="existing", is_active=True))
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            "/api/v1/membership-types/",
            json={"name": "Another", "slug": "existing"},
        )
        assert response.status_code == 409


class TestDefaultTier:
    """The tier new sign-ups land on, and the two rules the database enforces."""

    def test_a_second_default_is_rejected(self, db):
        db.add(MembershipType(name="First", slug="first", base_price=0, is_default=True))
        db.flush()

        db.add(MembershipType(name="Second", slug="second", base_price=0, is_default=True))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_a_priced_tier_cannot_be_the_default(self, db):
        db.add(MembershipType(name="Paid", slug="paid", base_price=50, is_default=True))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_raising_the_default_price_is_refused_rather_than_crashing(self, client, db):
        """Without the guard the check constraint would surface as a 500."""
        user = _create_user(db, "admin")
        mt = MembershipType(name="Free", slug="free", base_price=0, is_default=True)
        db.add(mt)
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            f"/api/v1/membership-types/{mt.id}", json={"base_price": 50.0}
        )

        assert response.status_code == 400

    def test_the_default_moves_to_the_tier_the_admin_picks(self, client, db):
        user = _create_user(db, "admin")
        current = MembershipType(name="Free", slug="free", base_price=0, is_default=True)
        wanted = MembershipType(name="Welcome", slug="welcome", base_price=0)
        db.add_all([current, wanted])
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            f"/api/v1/membership-types/{wanted.id}", json={"is_default": True}
        )

        assert response.status_code == 200
        assert response.json()["is_default"] is True
        db.expire_all()
        assert current.is_default is False

    def test_a_priced_tier_cannot_be_made_the_default(self, client, db):
        user = _create_user(db, "admin")
        mt = MembershipType(name="Premium", slug="premium", base_price=50)
        db.add(mt)
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            f"/api/v1/membership-types/{mt.id}", json={"is_default": True}
        )

        assert response.status_code == 400

    def test_the_default_cannot_be_left_unset(self, client, db):
        """A sign-up with no tier is barred from membership-restricted activities."""
        user = _create_user(db, "admin")
        mt = MembershipType(name="Free", slug="free", base_price=0, is_default=True)
        db.add(mt)
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.put(
            f"/api/v1/membership-types/{mt.id}", json={"is_default": False}
        )

        assert response.status_code == 400
        db.expire_all()
        assert mt.is_default is True

    def test_the_listing_says_which_tier_is_the_default(self, client, db):
        user = _create_user(db, "admin")
        db.add(MembershipType(name="Free", slug="free", base_price=0, is_default=True))
        db.add(MembershipType(name="Premium", slug="premium", base_price=50))
        db.flush()
        client.cookies.update(_auth_cookie(user))

        response = client.get("/api/v1/membership-types/")

        assert response.status_code == 200
        defaults = {t["name"]: t["is_default"] for t in response.json()}
        assert defaults["Free"] is True
        assert defaults["Premium"] is False


class TestAgeBand:
    """The age limits could not be set from the API at all; seeded values were
    the only way a tier got one (#291)."""

    @pytest.fixture
    def admin(self, client, db):
        user = _create_user(db, "admin")
        client.cookies.update(_auth_cookie(user))
        return user

    def test_created_with_an_age_band(self, client, admin):
        r = client.post(
            "/api/v1/membership-types/",
            json={"name": "Student", "slug": "student-age", "min_age": 16, "max_age": 25},
        )

        assert r.status_code == 201
        assert (r.json()["min_age"], r.json()["max_age"]) == (16, 25)

    def test_an_inverted_band_is_refused_on_create(self, client, admin):
        r = client.post(
            "/api/v1/membership-types/",
            json={"name": "Odd", "slug": "odd-age", "min_age": 30, "max_age": 20},
        )

        assert r.status_code == 422

    def test_one_end_is_checked_against_the_stored_other(self, client, db, admin):
        mt = MembershipType(name="Youth", slug="youth-age", max_age=15, is_active=True)
        db.add(mt)
        db.flush()

        r = client.put(f"/api/v1/membership-types/{mt.id}", json={"min_age": 18})

        assert r.status_code == 422
        db.refresh(mt)
        assert mt.min_age is None

    def test_null_clears_a_limit(self, client, db, admin):
        mt = MembershipType(name="Senior", slug="senior-age", min_age=65, is_active=True)
        db.add(mt)
        db.flush()

        r = client.put(f"/api/v1/membership-types/{mt.id}", json={"min_age": None, "max_age": 99})

        assert r.status_code == 200
        assert (r.json()["min_age"], r.json()["max_age"]) == (None, 99)


class TestAnExplicitNullBoolean:
    """A null boolean is refused at the edge rather than reaching the row (#565).

    Two different failures sat behind one status code. ``issues_card`` and
    ``is_default`` are NOT NULL, so the write was refused and the request 500ed
    with nothing lost. ``is_active`` is nullable, so the write *committed* and
    the reply then failed to serialise: the row was left holding NULL, and
    because the list validates every row through the same Response model, one
    request made ``GET /membership-types/`` 500 for every caller until the row
    was repaired by hand.

    Contrast ``TestAgeBand.test_null_clears_a_limit`` above: for ``min_age`` a
    null is the documented way to clear the limit. The rule is not "no nulls on
    an update", it is that a null must mean something the API can hand back.
    """

    @pytest.fixture
    def admin(self, client, db):
        user = _create_user(db, "admin")
        client.cookies.update(_auth_cookie(user))
        return user

    @pytest.fixture
    def tier(self, db):
        mt = MembershipType(name="Nullable", slug="nullable-bools", is_active=True)
        db.add(mt)
        db.flush()
        return mt

    @pytest.mark.parametrize("field", ["issues_card", "is_active", "is_default"])
    def test_it_is_refused_with_422(self, client, admin, tier, field):
        r = client.put(f"/api/v1/membership-types/{tier.id}", json={field: None})

        assert r.status_code == 422, f"{field}=null answered {r.status_code}"
        assert any(err["loc"][-1] == field for err in r.json()["detail"])

    @pytest.mark.parametrize("field", ["issues_card", "is_active", "is_default"])
    def test_the_row_is_untouched_and_the_list_still_answers(
        self, client, db, admin, tier, field
    ):
        """The half that made this worth a fix rather than a nicer status code."""
        before = getattr(tier, field)

        client.put(f"/api/v1/membership-types/{tier.id}", json={field: None})

        db.expire_all()
        row = db.query(MembershipType).filter(MembershipType.id == tier.id).first()
        assert getattr(row, field) == before
        assert client.get("/api/v1/membership-types/").status_code == 200

    def test_omitting_the_field_still_leaves_it_alone(self, client, admin, tier):
        """The guard must not turn a partial update into a full one."""
        r = client.put(
            f"/api/v1/membership-types/{tier.id}", json={"description": "Changed"}
        )

        assert r.status_code == 200, r.text
        assert r.json()["issues_card"] is False
        assert r.json()["is_active"] is True
