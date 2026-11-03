"""An activity price can apply to only some membership types (#427).

Membership type was wired to activity *access* and to price nowhere, so every
eligible member saw the same prices. A "member rate / general rate" pair of rows
therefore enforced nothing: the only check at registration was that the price
belonged to the activity, so any eligible member could select either.

The predicate that fixes it lives in one place — ``member_can_hold_price`` — and
is applied at two, because either alone leaves the gap open:

- **Serialization**, so the member is offered only their own prices. Two routes
  carry it: the activity detail and the prices list, both of which accept
  ``activities.read`` *or* ``self.activities.read``.
- **Registration**, because ``price_id`` arrives from the request body. A filter
  applied only on the way out is a suggestion.

The same predicate also closes #510: ``is_visible`` was enforced only in the
browser, so a member could register on a hidden price by posting its id. It is
one conjunct of the same question, and leaving it out would have meant writing a
known bypass into a brand-new guard.
"""

from datetime import datetime, timedelta, timezone

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.activities.models import Activity, ActivityPrice
from app.domains.activities.pricing import member_can_hold_price
from app.domains.auth.models import User
from app.domains.members.models import Member, MembershipType
from app.domains.persons.models import Person

SUFFIX = "@examplee6e3b1.com"


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id)}


def _type(db, name, slug):
    existing = db.query(MembershipType).filter(MembershipType.slug == slug).first()
    if existing:
        return existing
    mt = MembershipType(name=name, slug=slug, is_active=True)
    db.add(mt)
    db.flush()
    return mt


def _admin(db, suffix):
    person = Person(first_name="Price", last_name="Admin", email=f"pmt-admin{suffix}{SUFFIX}")
    db.add(person)
    db.flush()
    user = User(
        party_id=person.party_id,
        email=f"pmt-admin{suffix}{SUFFIX}",
        password_hash=hash_password("password123"),
        role="super_admin",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _member(db, suffix, membership_type_id):
    """A real member row. The activity tests' own ``_create_user`` makes a user
    with no member record, which is a different case — see
    ``TestAnAccountWithNoMemberRecord``."""
    person = Person(first_name="Price", last_name="Member", email=f"pmt-mem{suffix}{SUFFIX}")
    db.add(person)
    db.flush()
    user = User(
        party_id=person.party_id,
        email=f"pmt-mem{suffix}{SUFFIX}",
        password_hash=hash_password("password123"),
        role="member",
        is_active=True,
    )
    db.add(user)
    db.flush()
    member = Member(
        party_id=person.party_id,
        membership_type_id=membership_type_id,
        member_number=f"PMT{suffix}-{user.id}",
        status="active",
    )
    db.add(member)
    db.flush()
    return user, member


def _activity(db, slug, created_by_id):
    now = datetime.now(timezone.utc)
    activity = Activity(
        name="Priced Activity",
        slug=slug,
        starts_at=now + timedelta(days=10),
        ends_at=now + timedelta(days=11),
        registration_starts_at=now - timedelta(days=1),
        registration_ends_at=now + timedelta(days=9),
        max_participants=50,
        status="published",
        is_active=True,
        created_by=created_by_id,
    )
    db.add(activity)
    db.flush()
    return activity


def _price(db, activity, name, amount, **overrides):
    price = ActivityPrice(activity_id=activity.id, name=name, amount=amount, **overrides)
    db.add(price)
    db.flush()
    return price


class TestTheHoldablePredicate:
    """The one definition, exercised directly. The endpoint tests below prove it
    is actually reached; these pin what it means."""

    def test_a_price_with_no_types_applies_to_everyone(self, db):
        """NULL means every type, which is what keeps every price written before
        this column existed working untouched."""
        admin = _admin(db, "-pred-open")
        full = _type(db, "Full-pred", "full-pred")
        activity = _activity(db, "pred-open", admin.id)
        price = _price(db, activity, "Open", 10)
        _, member = _member(db, "-pred-open", full.id)

        assert price.membership_type_ids is None
        assert member_can_hold_price(price, member) is True

    def test_an_empty_list_also_applies_to_everyone(self, db):
        """The admin form sends `[]` to clear a restriction, so empty has to mean
        the same as absent rather than 'no type at all'."""
        admin = _admin(db, "-pred-empty")
        full = _type(db, "Full-pred2", "full-pred2")
        activity = _activity(db, "pred-empty", admin.id)
        price = _price(db, activity, "Open", 10, membership_type_ids=[])
        _, member = _member(db, "-pred-empty", full.id)

        assert member_can_hold_price(price, member) is True

    def test_a_restricted_price_is_held_by_a_listed_type(self, db):
        admin = _admin(db, "-pred-in")
        full = _type(db, "Full-pred3", "full-pred3")
        activity = _activity(db, "pred-in", admin.id)
        price = _price(db, activity, "Members", 10, membership_type_ids=[full.id])
        _, member = _member(db, "-pred-in", full.id)

        assert member_can_hold_price(price, member) is True

    def test_a_restricted_price_is_not_held_by_another_type(self, db):
        admin = _admin(db, "-pred-out")
        full = _type(db, "Full-pred4", "full-pred4")
        friend = _type(db, "Friend-pred4", "friend-pred4")
        activity = _activity(db, "pred-out", admin.id)
        price = _price(db, activity, "Members", 10, membership_type_ids=[full.id])
        _, member = _member(db, "-pred-out", friend.id)

        assert member_can_hold_price(price, member) is False

    def test_a_member_with_no_type_holds_only_unrestricted_prices(self, db):
        """Deliberate: a restriction naming specific types cannot be said to
        include a member who has none. `membership_type_id` is nullable, so this
        member is a legitimate record."""
        admin = _admin(db, "-pred-none")
        full = _type(db, "Full-pred5", "full-pred5")
        activity = _activity(db, "pred-none", admin.id)
        restricted = _price(db, activity, "Members", 10, membership_type_ids=[full.id])
        open_price = _price(db, activity, "Open", 20)
        _, member = _member(db, "-pred-none", None)

        assert member_can_hold_price(restricted, member) is False
        assert member_can_hold_price(open_price, member) is True

    def test_an_inactive_price_is_never_held(self, db):
        admin = _admin(db, "-pred-inactive")
        full = _type(db, "Full-pred6", "full-pred6")
        activity = _activity(db, "pred-inactive", admin.id)
        price = _price(db, activity, "Retired", 10, is_active=False)
        _, member = _member(db, "-pred-inactive", full.id)

        assert member_can_hold_price(price, member) is False

    def test_a_hidden_price_is_never_held(self, db):
        """#510. This conjunct had no server-side enforcement at all."""
        admin = _admin(db, "-pred-hidden")
        full = _type(db, "Full-pred7", "full-pred7")
        activity = _activity(db, "pred-hidden", admin.id)
        price = _price(db, activity, "Hidden", 10, is_visible=False)
        _, member = _member(db, "-pred-hidden", full.id)

        assert member_can_hold_price(price, member) is False


class TestTheMemberIsOfferedOnlyTheirOwnPrices:
    """Decision 4 on #427: the member portal shows only the member's own prices.

    Both routes that serve prices accept `activities.read` or
    `self.activities.read`, so both have to narrow by permission.
    """

    def _two_tier_activity(self, db, suffix):
        admin = _admin(db, suffix)
        full = _type(db, f"Full{suffix}", f"full{suffix}")
        friend = _type(db, f"Friend{suffix}", f"friend{suffix}")
        activity = _activity(db, f"two-tier{suffix}", admin.id)
        members_price = _price(
            db, activity, "Members", 10, membership_type_ids=[full.id], display_order=0
        )
        general_price = _price(
            db, activity, "General", 25, membership_type_ids=[friend.id], display_order=1
        )
        return admin, full, friend, activity, members_price, general_price

    def test_the_detail_route_offers_only_the_members_own_price(self, client, db):
        _, full, _, activity, members_price, general_price = self._two_tier_activity(
            db, "-detail"
        )
        user, _ = _member(db, "-detail", full.id)
        client.cookies.update(_auth_cookie(user))

        prices = client.get(f"/api/v1/activities/{activity.id}").json()["prices"]

        assert [p["id"] for p in prices] == [members_price.id], (
            "the member was offered a price their type is excluded from; "
            "decision 4 on #427 is that they see only their own"
        )
        assert general_price.id not in [p["id"] for p in prices]

    def test_the_prices_route_narrows_the_same_way(self, client, db):
        """The second route, and the one easy to miss: a member who cannot see a
        price on the detail response could otherwise just ask for the list."""
        _, full, _, activity, members_price, _ = self._two_tier_activity(db, "-list")
        user, _ = _member(db, "-list", full.id)
        client.cookies.update(_auth_cookie(user))

        listed = client.get(f"/api/v1/activities/{activity.id}/prices").json()

        assert [p["id"] for p in listed] == [members_price.id]

    def test_an_admin_sees_every_price_on_both_routes(self, client, db):
        """The mirror, and the reason the filter is by permission rather than by
        endpoint: an admin managing prices must see the ones they cannot hold,
        or they could not edit them."""
        admin, _, _, activity, members_price, general_price = self._two_tier_activity(
            db, "-admin"
        )
        client.cookies.update(_auth_cookie(admin))

        detail = client.get(f"/api/v1/activities/{activity.id}").json()["prices"]
        listed = client.get(f"/api/v1/activities/{activity.id}/prices").json()

        both = {members_price.id, general_price.id}
        assert {p["id"] for p in detail} == both
        assert {p["id"] for p in listed} == both

    def test_an_admin_who_is_also_a_member_still_sees_every_price(self, client, db):
        """The case that proves the exemption is the *permission*.

        The admin in the test above has no member record, so it cannot tell
        "exempted because they hold `activities.read`" from "exempted because
        there was no member row to filter by" — a mutation removing the
        permission check passed it. A club admin who is also a member of the
        club is both realistic and the case where precedence matters: their own
        type excludes the members' price, and they must still see it to manage
        it.
        """
        activity_admin = _admin(db, "-admin-member")
        full = _type(db, "Full-am", "full-am")
        friend = _type(db, "Friend-am", "friend-am")
        activity = _activity(db, "admin-member", activity_admin.id)
        members_price = _price(db, activity, "Members", 10, membership_type_ids=[full.id])
        general_price = _price(db, activity, "General", 25, membership_type_ids=[friend.id])

        # Give the admin account a member record on the *friend* tier, so the
        # members-only price is one their own type cannot hold.
        person = db.query(Person).filter(Person.party_id == activity_admin.party_id).first()
        db.add(
            Member(
                party_id=person.party_id,
                membership_type_id=friend.id,
                member_number=f"PMTAM-{activity_admin.id}",
                status="active",
            )
        )
        db.flush()
        client.cookies.update(_auth_cookie(activity_admin))

        detail = client.get(f"/api/v1/activities/{activity.id}").json()["prices"]
        listed = client.get(f"/api/v1/activities/{activity.id}/prices").json()

        both = {members_price.id, general_price.id}
        assert {p["id"] for p in detail} == both, (
            "an admin who is also a member was narrowed to their own tier, so "
            "they cannot see or edit the price they do not hold"
        )
        assert {p["id"] for p in listed} == both

    def test_a_hidden_price_is_not_served_to_the_member(self, client, db):
        """#510: the hidden price was in the detail response, so its id did not
        even have to be guessed."""
        admin = _admin(db, "-hidden-serve")
        full = _type(db, "Full-hs", "full-hs")
        activity = _activity(db, "hidden-serve", admin.id)
        visible = _price(db, activity, "Visible", 10)
        hidden = _price(db, activity, "Hidden", 1, is_visible=False)
        user, _ = _member(db, "-hidden-serve", full.id)
        client.cookies.update(_auth_cookie(user))

        prices = client.get(f"/api/v1/activities/{activity.id}").json()["prices"]

        assert [p["id"] for p in prices] == [visible.id]
        assert hidden.id not in [p["id"] for p in prices]


class TestRegistrationRefusesAPriceTheMemberMayNotHold:
    """The choke point that makes the column real rather than cosmetic.

    `price_id` comes from the request body, so these refusals cannot rest on
    what the member was offered.
    """

    def test_registering_on_another_types_price_is_refused(self, client, db):
        """The member **has** a price of their own here, deliberately.

        With only the restricted price on the activity, the eligibility check
        refuses them first for having no applicable price at all, and this test
        would pass on a registration endpoint that never consults the predicate
        — which is exactly what a mutation run showed. Giving them their own
        price makes them eligible, so the 400 can only come from the price
        guard.
        """
        admin = _admin(db, "-reg-wrong")
        full = _type(db, "Full-rw", "full-rw")
        friend = _type(db, "Friend-rw", "friend-rw")
        activity = _activity(db, "reg-wrong", admin.id)
        members_price = _price(db, activity, "Members", 10, membership_type_ids=[full.id])
        _price(db, activity, "General", 25, membership_type_ids=[friend.id])
        user, _ = _member(db, "-reg-wrong", friend.id)
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": members_price.id},
        )

        assert response.status_code == 400, (
            "a member registered on a price reserved for another membership "
            "type by posting its id; the column would be decoration"
        )

    def test_registering_on_a_hidden_price_is_refused(self, client, db):
        """#510, at the point it actually mattered."""
        admin = _admin(db, "-reg-hidden")
        full = _type(db, "Full-rh", "full-rh")
        activity = _activity(db, "reg-hidden", admin.id)
        _price(db, activity, "Visible", 50)
        hidden = _price(db, activity, "Hidden", 1, is_visible=False)
        user, _ = _member(db, "-reg-hidden", full.id)
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": hidden.id},
        )

        assert response.status_code == 400, (
            "a member registered on a hidden price by posting its id, paying 1 "
            "instead of 50"
        )

    def test_registering_on_your_own_types_price_still_works(self, client, db):
        """The mirror. Without it every refusal above would be satisfied by a
        registration endpoint that rejects everything."""
        admin = _admin(db, "-reg-ok")
        full = _type(db, "Full-ro", "full-ro")
        friend = _type(db, "Friend-ro", "friend-ro")
        activity = _activity(db, "reg-ok", admin.id)
        members_price = _price(db, activity, "Members", 10, membership_type_ids=[full.id])
        _price(db, activity, "General", 25, membership_type_ids=[friend.id])
        user, _ = _member(db, "-reg-ok", full.id)
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": members_price.id},
        )

        assert response.status_code == 201, response.text
        assert response.json()["price_id"] == members_price.id

    def test_an_unrestricted_price_is_still_registerable(self, client, db):
        """The upgrade path: every price that existed before this column keeps
        working for everyone."""
        admin = _admin(db, "-reg-open")
        full = _type(db, "Full-rop", "full-rop")
        activity = _activity(db, "reg-open", admin.id)
        price = _price(db, activity, "Open", 10)
        user, _ = _member(db, "-reg-open", full.id)
        client.cookies.update(_auth_cookie(user))

        response = client.post(
            f"/api/v1/activities/{activity.id}/register",
            json={"price_id": price.id},
        )

        assert response.status_code == 201, response.text


class TestNoPriceForTheMembersType:
    """The decision taken on #427 over falling back to a default price.

    It has to be a stated reason rather than a silent empty list: the member now
    sees only their own prices, so a misconfigured activity would otherwise
    render as one with no prices and no explanation.
    """

    def test_the_member_is_blocked_with_a_named_reason(self, client, db):
        admin = _admin(db, "-elig-none")
        full = _type(db, "Full-en", "full-en")
        friend = _type(db, "Friend-en", "friend-en")
        activity = _activity(db, "elig-none", admin.id)
        _price(db, activity, "Members only", 10, membership_type_ids=[full.id])
        user, _ = _member(db, "-elig-none", friend.id)
        client.cookies.update(_auth_cookie(user))

        body = client.get(f"/api/v1/activities/{activity.id}/eligibility").json()

        assert body["eligible"] is False
        assert "no_price_for_membership_type" in [d["code"] for d in body["details"]], (
            "the member saw an activity with no price and no reason given"
        )

    def test_an_activity_with_no_prices_at_all_is_not_blamed_on_the_type(
        self, client, db
    ):
        """The boundary of this reason, drawn deliberately.

        An activity with no price rows is a different situation from one whose
        prices exclude this member, and the message would misdescribe it —
        nothing is being withheld from their type. It is also pre-existing
        behaviour: `price_id` is required on the register request, so such an
        activity was never registerable, and #427 is not the place to change
        what happens there.
        """
        admin = _admin(db, "-elig-empty")
        full = _type(db, "Full-ee", "full-ee")
        activity = _activity(db, "elig-empty", admin.id)
        user, _ = _member(db, "-elig-empty", full.id)
        client.cookies.update(_auth_cookie(user))

        body = client.get(f"/api/v1/activities/{activity.id}/eligibility").json()

        assert "no_price_for_membership_type" not in [
            d["code"] for d in body["details"]
        ], "an activity with no prices was reported as excluding the member's type"

    def test_a_member_whose_type_has_a_price_is_eligible(self, client, db):
        """The mirror: the reason must not fire whenever a price is restricted
        at all, only when none of them reaches this member."""
        admin = _admin(db, "-elig-ok")
        full = _type(db, "Full-eo", "full-eo")
        activity = _activity(db, "elig-ok", admin.id)
        _price(db, activity, "Members", 10, membership_type_ids=[full.id])
        user, _ = _member(db, "-elig-ok", full.id)
        client.cookies.update(_auth_cookie(user))

        body = client.get(f"/api/v1/activities/{activity.id}/eligibility").json()

        assert "no_price_for_membership_type" not in [
            d["code"] for d in body["details"]
        ], body
