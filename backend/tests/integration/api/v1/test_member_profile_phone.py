"""``PUT /members/me/profile`` writes the member's mobile as a primary contact.

The portal offers no "primary" choice: ``ProfileUpdate`` carries only gender and
phone, and the handler hardcodes ``is_primary=True`` on the insert. So a member
who just types their mobile number lands on
``uq_contacts_one_primary_per_channel`` whenever staff already entered a primary
home phone, because both types share the ``phone`` channel.
"""

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.members.models import Member
from app.domains.persons.models import Contact, ContactType, Person


def _member_user(db, email):
    person = Person(first_name="Port", last_name="Al", email=email)
    db.add(person)
    db.flush()
    user = User(
        party_id=person.party_id,
        email=email,
        password_hash=hash_password("password123"),
        role="member",
        is_active=True,
    )
    db.add(user)
    db.add(Member(party_id=person.party_id, status="active"))
    db.flush()
    return user, person


def _contact_type(db, code, channel, name):
    ct = db.query(ContactType).filter(ContactType.code == code).first()
    if not ct:
        ct = ContactType(code=code, name=name, channel=channel, is_active=True)
        db.add(ct)
        db.flush()
    return ct


def _login(client, user):
    client.cookies.update({"access_token": create_access_token(user.id)})


class TestMemberSetsTheirOwnPhone:
    def test_a_staff_entered_primary_home_phone_is_demoted(self, client, db):
        """The member is the better authority on how to reach them, so their
        mobile takes the primary slot and the home phone keeps its place in the
        list without it."""
        user, person = _member_user(db, "portal-phone@examplee6e3b1.com")
        home = _contact_type(db, "phone_home", "phone", "Home Phone")
        _contact_type(db, "phone_mobile", "phone", "Mobile Phone")
        incumbent = Contact(
            party_id=person.party_id,
            contact_type_id=home.id,
            value="+34 900 111 222",
            is_primary=True,
        )
        db.add(incumbent)
        db.flush()
        _login(client, user)

        response = client.put(
            "/api/v1/members/me/profile", json={"phone": "+34 600 111 222"}
        )

        assert response.status_code == 200
        assert response.json()["phone"] == "+34 600 111 222"
        db.refresh(incumbent)
        assert incumbent.is_primary is False

    def test_a_member_with_no_phone_at_all_still_works(self, client, db):
        user, _ = _member_user(db, "portal-phone-empty@examplee6e3b1.com")
        _contact_type(db, "phone_mobile", "phone", "Mobile Phone")
        _login(client, user)

        response = client.put(
            "/api/v1/members/me/profile", json={"phone": "+34 600 333 444"}
        )

        assert response.status_code == 200
        assert response.json()["phone"] == "+34 600 333 444"

    def test_editing_an_existing_mobile_leaves_the_primary_flag_alone(self, client, db):
        """The handler updates an existing ``phone_mobile`` in place, so the
        demotion is a cross-type event rather than something every edit
        triggers."""
        user, person = _member_user(db, "portal-phone-edit@examplee6e3b1.com")
        mobile = _contact_type(db, "phone_mobile", "phone", "Mobile Phone")
        existing = Contact(
            party_id=person.party_id,
            contact_type_id=mobile.id,
            value="+34 600 555 666",
            is_primary=True,
        )
        db.add(existing)
        db.flush()
        _login(client, user)

        response = client.put(
            "/api/v1/members/me/profile", json={"phone": "+34 600 777 888"}
        )

        assert response.status_code == 200
        db.refresh(existing)
        assert existing.value == "+34 600 777 888"
        assert existing.is_primary is True
