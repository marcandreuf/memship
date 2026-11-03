"""Integration tests for the digital member card + QR check-in (v0.7.0)."""

from app.core.security.card_token import sign_card_token, verify_card_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


def _auth_cookie(user):
    from app.core.security.jwt import create_access_token

    return {"access_token": create_access_token(user.id)}


def _ensure_org(db, *, member_card=True, prefix="", padding=4, next_num=1):
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
    org.features = {"member_card": member_card} if member_card else {}
    org.member_number_prefix = prefix
    org.member_number_padding = padding
    org.member_number_next = next_num
    db.flush()
    return org


def _create_admin(db, email="admin-card@examplee6e3b1.com"):
    person = Person(first_name="Admin", last_name="Card", email=email)
    db.add(person)
    db.flush()
    user = User(
        party_id=person.party_id,
        email=email,
        password_hash=hash_password("password123"),
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _create_member_user(
    db,
    email="member-card@examplee6e3b1.com",
    status="active",
    number="SCB-0001",
    type_name=None,
    with_type=True,
    issues_card=True,
):
    """``with_type=False`` leaves `membership_type_id` null, which the column
    allows (`ondelete="SET NULL"`) and a staff-created record really has."""
    person = Person(first_name="Mika", last_name="Roig", email=email)
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
    db.flush()

    mt = None
    if with_type and type_name:
        mt = db.query(MembershipType).filter(MembershipType.name == type_name).first()
        if not mt:
            mt = MembershipType(
                name=type_name, slug=type_name.lower().replace(" ", "-"), is_active=True
            )
            db.add(mt)
            db.flush()
    elif with_type:
        mt = db.query(MembershipType).first()
        if not mt:
            mt = MembershipType(name="General", slug="general", is_active=True)
            db.add(mt)
            db.flush()
    # Opt the type in, the way a real admin now has to. Since #428 Part 2 the
    # switch is off on every type, so a fixture that does not set it is testing
    # an instance that issues no cards — which is what
    # `TestTheCardIsWithheldPerType` is for.
    if mt is not None and issues_card:
        mt.issues_card = True
        db.flush()

    member = Member(
        party_id=person.party_id,
        membership_type_id=mt.id if mt else None,
        member_number=number,
        status=status,
    )
    db.add(member)
    db.flush()
    return user, member


# --- Card token unit behaviour ---


class TestCardToken:
    def test_sign_verify_roundtrip(self):
        token = sign_card_token(123)
        assert token.startswith("123.")
        assert verify_card_token(token) == 123

    def test_tampered_or_malformed_rejected(self):
        token = sign_card_token(7)
        tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
        assert verify_card_token(tampered) is None       # bad signature
        assert verify_card_token("7.deadbeef") is None    # wrong signature
        assert verify_card_token("notanumber.abc") is None  # non-int id
        assert verify_card_token("garbage") is None        # no separator
        assert verify_card_token("") is None               # empty
        assert verify_card_token("0.abc") is None          # non-positive id


# --- Member card endpoints ---


class TestMemberCard:
    def test_get_my_card_fields(self, client, db):
        _ensure_org(db, prefix="SCB-")
        user, member = _create_member_user(db)
        client.cookies.update(_auth_cookie(user))

        resp = client.get("/api/v1/me/card")
        assert resp.status_code == 200
        data = resp.json()
        assert data["member_id"] == member.id
        assert data["full_name"] == "Mika Roig"
        assert data["member_number"] == "SCB-0001"
        assert data["status"] == "active"
        assert data["organization"]["name"] == "Test Club"
        assert data["organization"]["brand_color"] == "#0083ad"
        assert verify_card_token(data["token"]) == member.id

    def test_non_member_gets_403(self, client, db):
        _ensure_org(db)
        admin = _create_admin(db)  # admin user with no Member row
        client.cookies.update(_auth_cookie(admin))

        resp = client.get("/api/v1/me/card")
        assert resp.status_code == 403

    def test_qr_svg_returns_svg(self, client, db):
        _ensure_org(db)
        user, _ = _create_member_user(db)
        client.cookies.update(_auth_cookie(user))

        resp = client.get("/api/v1/me/card/qr.svg")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("image/svg+xml")
        assert b"<svg" in resp.content

    def test_pdf_returns_application_pdf(self, client, db):
        _ensure_org(db)
        user, _ = _create_member_user(db)
        client.cookies.update(_auth_cookie(user))

        resp = client.get("/api/v1/me/card/pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:5] == b"%PDF-"

    def test_card_404_when_module_off(self, client, db):
        _ensure_org(db, member_card=False)
        user, _ = _create_member_user(db)
        client.cookies.update(_auth_cookie(user))

        assert client.get("/api/v1/me/card").status_code == 404
        assert client.get("/api/v1/me/card/qr.svg").status_code == 404


# --- Admin scan ---


class TestScan:
    def test_scan_valid_returns_member_status(self, client, db):
        _ensure_org(db)
        admin = _create_admin(db)
        _user, member = _create_member_user(db)
        token = sign_card_token(member.id)
        client.cookies.update(_auth_cookie(admin))

        resp = client.post("/api/v1/card/scan", json={"token": token})
        assert resp.status_code == 200
        data = resp.json()
        assert data["member_id"] == member.id
        assert data["full_name"] == "Mika Roig"
        assert data["member_number"] == "SCB-0001"
        assert data["status"] == "active"

    def test_scan_reflects_live_suspension(self, client, db):
        _ensure_org(db)
        admin = _create_admin(db)
        _user, member = _create_member_user(db)
        token = sign_card_token(member.id)
        client.cookies.update(_auth_cookie(admin))

        # Card was "issued" while active; suspend after the fact.
        member.status = "suspended"
        db.flush()

        resp = client.post("/api/v1/card/scan", json={"token": token})
        assert resp.status_code == 200
        assert resp.json()["status"] == "suspended"

    def test_scan_invalid_signature_400(self, client, db):
        _ensure_org(db)
        admin = _create_admin(db)
        _create_member_user(db)
        client.cookies.update(_auth_cookie(admin))

        resp = client.post("/api/v1/card/scan", json={"token": "1.deadbeef"})
        assert resp.status_code == 400

    def test_scan_unknown_member_404(self, client, db):
        _ensure_org(db)
        admin = _create_admin(db)
        client.cookies.update(_auth_cookie(admin))

        token = sign_card_token(999999)  # correctly signed, no such member
        resp = client.post("/api/v1/card/scan", json={"token": token})
        assert resp.status_code == 404

    def test_member_cannot_scan(self, client, db):
        _ensure_org(db)
        user, member = _create_member_user(db)
        client.cookies.update(_auth_cookie(user))

        resp = client.post(
            "/api/v1/card/scan", json={"token": sign_card_token(member.id)}
        )
        assert resp.status_code == 403

    def test_scan_404_when_module_off(self, client, db):
        _ensure_org(db, member_card=False)
        admin = _create_admin(db)
        _user, member = _create_member_user(db)
        client.cookies.update(_auth_cookie(admin))

        resp = client.post(
            "/api/v1/card/scan", json={"token": sign_card_token(member.id)}
        )
        assert resp.status_code == 404


# --- Admin: view/print any member's card ---


class TestAdminMemberCard:
    def test_admin_gets_member_card(self, client, db):
        _ensure_org(db)
        admin = _create_admin(db)
        _user, member = _create_member_user(db)
        client.cookies.update(_auth_cookie(admin))

        resp = client.get(f"/api/v1/members/{member.id}/card")
        assert resp.status_code == 200
        data = resp.json()
        assert data["member_id"] == member.id
        assert data["full_name"] == "Mika Roig"
        assert data["member_number"] == "SCB-0001"
        assert verify_card_token(data["token"]) == member.id

    def test_admin_gets_member_card_pdf(self, client, db):
        _ensure_org(db)
        admin = _create_admin(db)
        _user, member = _create_member_user(db)
        client.cookies.update(_auth_cookie(admin))

        resp = client.get(f"/api/v1/members/{member.id}/card/pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:5] == b"%PDF-"

    def test_admin_card_works_for_member_without_user_account(self, client, db):
        # Members without a login (e.g. minors) still get a printable card.
        _ensure_org(db)
        admin = _create_admin(db)
        _user, member = _create_member_user(db)
        member.user_id = None
        db.flush()
        client.cookies.update(_auth_cookie(admin))

        resp = client.get(f"/api/v1/members/{member.id}/card")
        assert resp.status_code == 200
        assert resp.json()["member_id"] == member.id

    def test_member_cannot_view_admin_card_endpoint(self, client, db):
        _ensure_org(db)
        user, member = _create_member_user(db)
        client.cookies.update(_auth_cookie(user))

        resp = client.get(f"/api/v1/members/{member.id}/card")
        assert resp.status_code == 403

    def test_admin_card_unknown_member_404(self, client, db):
        _ensure_org(db)
        admin = _create_admin(db)
        client.cookies.update(_auth_cookie(admin))

        resp = client.get("/api/v1/members/999999/card")
        assert resp.status_code == 404

    def test_admin_card_404_when_module_off(self, client, db):
        _ensure_org(db, member_card=False)
        admin = _create_admin(db)
        _user, member = _create_member_user(db)
        client.cookies.update(_auth_cookie(admin))

        assert client.get(f"/api/v1/members/{member.id}/card").status_code == 404
        assert client.get(f"/api/v1/members/{member.id}/card/pdf").status_code == 404


# --- Member numbering ---


class TestMemberNumbering:
    def test_auto_number_on_create_uses_config(self, client, db):
        _ensure_org(db, prefix="SCB-", padding=4, next_num=1)
        admin = _create_admin(db)
        client.cookies.update(_auth_cookie(admin))

        resp = client.post(
            "/api/v1/members/",
            json={"first_name": "New", "last_name": "One"},
        )
        assert resp.status_code == 201
        assert resp.json()["member_number"] == "SCB-0001"

    def test_allocation_advances_and_is_unique(self, client, db):
        _ensure_org(db, prefix="SCB-", padding=4, next_num=1)
        admin = _create_admin(db)
        client.cookies.update(_auth_cookie(admin))

        numbers = []
        for i in range(3):
            resp = client.post(
                "/api/v1/members/",
                json={"first_name": f"P{i}", "last_name": "X"},
            )
            assert resp.status_code == 201
            numbers.append(resp.json()["member_number"])

        assert numbers == ["SCB-0001", "SCB-0002", "SCB-0003"]
        assert len(set(numbers)) == 3

    def test_allocation_skips_existing_collision(self, client, db):
        _ensure_org(db, prefix="SCB-", padding=4, next_num=1)
        # Pre-seed a member already holding SCB-0001.
        _create_member_user(db, email="held@examplee6e3b1.com", number="SCB-0001")
        admin = _create_admin(db)
        client.cookies.update(_auth_cookie(admin))

        resp = client.post(
            "/api/v1/members/",
            json={"first_name": "Next", "last_name": "Free"},
        )
        assert resp.status_code == 201
        assert resp.json()["member_number"] == "SCB-0002"

    def test_assign_numbers_fills_nulls_in_id_order(self, client, db):
        _ensure_org(db, prefix="SCB-", padding=4, next_num=1)
        admin = _create_admin(db)

        # Two members with NULL member_number, created in a known id order.
        m1 = _create_member_user(db, email="m1@examplee6e3b1.com", number=None)[1]
        m2 = _create_member_user(db, email="m2@examplee6e3b1.com", number=None)[1]
        client.cookies.update(_auth_cookie(admin))

        resp = client.post("/api/v1/members/assign-numbers")
        assert resp.status_code == 200
        assert resp.json()["assigned"] == 2

        db.refresh(m1)
        db.refresh(m2)
        assert m1.member_number == "SCB-0001"
        assert m2.member_number == "SCB-0002"

    def test_assign_numbers_requires_admin(self, client, db):
        _ensure_org(db)
        user, _ = _create_member_user(db)
        client.cookies.update(_auth_cookie(user))

        resp = client.post("/api/v1/members/assign-numbers")
        assert resp.status_code == 403


class TestTheCardShowsTheMembershipType:
    """Part 1 of #428. The card carried name, number, status, photo and branding
    but never the type, so every card looked the same whoever held it — and an
    organisation with a free supporter tier beside a full one could not tell them
    apart at its own door.

    Unconditional on purpose: it is information the holder and the person
    checking both want, and it does not touch the per-type issuing question that
    Part 2 settles.
    """

    def test_my_card_carries_the_type_name(self, client, db):
        _ensure_org(db, prefix="SCB-")
        user, _ = _create_member_user(db, type_name="Student")
        client.cookies.update(_auth_cookie(user))

        resp = client.get("/api/v1/me/card")

        assert resp.status_code == 200
        assert resp.json()["membership_type"] == "Student"

    def test_the_admin_card_carries_the_type_name(self, client, db):
        _ensure_org(db)
        admin = _create_admin(db)
        _, member = _create_member_user(
            db, email="type-admin@examplee6e3b1.com", type_name="Honorary"
        )
        client.cookies.update(_auth_cookie(admin))

        resp = client.get(f"/api/v1/members/{member.id}/card")

        assert resp.status_code == 200
        assert resp.json()["membership_type"] == "Honorary"

    def test_the_scan_result_carries_the_type_name(self, client, db):
        """The readout whoever is checking the card actually looks at."""
        _ensure_org(db)
        admin = _create_admin(db)
        _, member = _create_member_user(
            db, email="type-scan@examplee6e3b1.com", type_name="Supporter"
        )
        client.cookies.update(_auth_cookie(admin))

        resp = client.post(
            "/api/v1/card/scan", json={"token": sign_card_token(member.id)}
        )

        assert resp.status_code == 200
        assert resp.json()["membership_type"] == "Supporter"

    def test_build_card_still_renders_a_member_with_no_type(self, db):
        """`membership_type_id` is nullable, so reading
        `member.membership_type.name` unguarded would raise `AttributeError`.

        Asserted against `build_card` rather than through an endpoint, because
        **#428 Part 2 made that case unreachable over the API**: a member with no
        type has no type whose card switch was turned on, so every card route now
        refuses them — which is `TestTheCardIsWithheldPerType` below. The guard
        in `build_card` stays: it is a service function, the column is still
        nullable, and the cost of keeping it is one conditional.
        """
        from app.domains.member_card.service import build_card

        _ensure_org(db)
        _, member = _create_member_user(
            db, email="type-none@examplee6e3b1.com", with_type=False
        )

        card = build_card(db, member)

        assert card["membership_type"] is None
        assert card["member_number"]


class TestThePrintedCardShowsTheMembershipType:
    """The PDF is rendered from `member_card.html` through the same Jinja
    environment the service uses, so the template is asserted directly rather
    than through WeasyPrint's output bytes — a type name is not reliably
    greppable in a compressed PDF, and the question here is what the template
    emits."""

    def _render(self, membership_type):
        from app.domains.member_card.service import _env

        return _env.get_template("member_card.html").render(
            card={
                "full_name": "Mika Roig",
                "member_number": "SCB-0001",
                "membership_type": membership_type,
                "status": "active",
                "organization": {"name": "Test Club", "brand_color": "#0083ad"},
            },
            qr_svg="<svg></svg>",
            photo_data_uri=None,
            initials="MR",
        )

    def test_the_type_is_printed(self):
        assert "Student" in self._render("Student")

    def test_no_type_prints_no_line_at_all(self):
        """Omitted rather than printed empty or as "no type": the card is a
        credential, and a blank tier line on one reads as a misprint. The scan
        readout makes the opposite choice on purpose, because whoever is checking
        needs "this member has no type" to differ from a line that did not
        render."""
        html = self._render(None)

        assert 'class="type"' not in html
        assert "SCB-0001" in html, "the number should still render"


class TestTheCardIsWithheldPerType:
    """Part 2 of #428. The card is issued per membership type, off everywhere
    until an admin turns it on.

    The organisation's case: a free "friend" tier beside a paid one, where the
    card *is* what the paid tier buys — *"porque no damos clases ni tienen
    obligación, entonces hay que darles algo a cambio"*. Withholding it is the
    only thing that actually reserves the benefit, since the requester's own
    answer was that shops will not check the tier printed on it.

    **Hide, not mark invalid**, decided on the issue: 404 like the instance-wide
    gate, because a card this member does not have is absent rather than
    forbidden.
    """

    def _member_on_a_type_without_cards(self, db, email):
        return _create_member_user(db, email=email, type_name="Friends", issues_card=False)

    def test_the_member_cannot_reach_their_own_card(self, client, db):
        _ensure_org(db)
        user, _ = self._member_on_a_type_without_cards(db, "withheld-me@examplee6e3b1.com")
        client.cookies.update(_auth_cookie(user))

        assert client.get("/api/v1/me/card").status_code == 404

    def test_the_qr_and_the_pdf_go_with_it(self, client, db):
        """*"One switch governs everything that hangs off the card, not a part of
        it."* A reachable PDF would be a card by another route."""
        _ensure_org(db)
        user, _ = self._member_on_a_type_without_cards(db, "withheld-qr@examplee6e3b1.com")
        client.cookies.update(_auth_cookie(user))

        assert client.get("/api/v1/me/card/qr.svg").status_code == 404
        assert client.get("/api/v1/me/card/pdf").status_code == 404

    def test_an_admin_cannot_print_one_either(self, client, db):
        """The target member's type, not the admin's permissions. Otherwise the
        admin PDF stays a way to produce a card the policy says should not
        exist — which the issue names as the check easiest to get wrong."""
        _ensure_org(db)
        admin = _create_admin(db, email="withheld-admin@examplee6e3b1.com")
        _, member = self._member_on_a_type_without_cards(
            db, "withheld-target@examplee6e3b1.com"
        )
        client.cookies.update(_auth_cookie(admin))

        assert client.get(f"/api/v1/members/{member.id}/card").status_code == 404
        assert client.get(f"/api/v1/members/{member.id}/card/qr.svg").status_code == 404
        assert client.get(f"/api/v1/members/{member.id}/card/pdf").status_code == 404

    def test_a_member_with_no_type_at_all_is_withheld_too(self, client, db):
        """The stricter reading, and the only one that does not leave a loophole.

        The issue leaves this one open. Taking the permissive reading would mean
        every *typed* member waits for an admin to tick their type while a member
        with no type is issued a card immediately — backwards for a feature whose
        purpose is withholding. It matches the same call on per-type pricing,
        where a restriction naming types cannot include a member who has none.
        """
        _ensure_org(db)
        user, _ = _create_member_user(
            db, email="withheld-notype@examplee6e3b1.com", with_type=False
        )
        client.cookies.update(_auth_cookie(user))

        assert client.get("/api/v1/me/card").status_code == 404

    def test_turning_the_type_on_issues_the_card(self, client, db):
        """The mirror. Without it every refusal above would be satisfied by a
        card module that never works for anyone."""
        _ensure_org(db)
        user, member = _create_member_user(
            db, email="issued@examplee6e3b1.com", type_name="Full", issues_card=True
        )
        client.cookies.update(_auth_cookie(user))

        response = client.get("/api/v1/me/card")

        assert response.status_code == 200, response.text
        assert response.json()["member_id"] == member.id

    def test_the_instance_flag_still_governs_above_the_type(self, client, db):
        """Two levels with distinct meanings, which is the decision on #428: the
        flag answers whether the card module exists on this instance at all, the
        type answers whether a given member gets one. A type with the switch on
        must still 404 while the module is off, or the flag has stopped being a
        module gate."""
        _ensure_org(db, member_card=False)
        user, _ = _create_member_user(
            db, email="flagoff@examplee6e3b1.com", type_name="Full", issues_card=True
        )
        client.cookies.update(_auth_cookie(user))

        assert client.get("/api/v1/me/card").status_code == 404


class TestAStaleQrStopsVerifying:
    """The consequence the issue calls easiest to miss.

    A card token is signed once and never expires, so a QR captured while the
    holder's type still issued cards would keep verifying at the door after an
    admin switched that type off. `verify_scan` already re-read status live; it
    now re-reads the type too, or the switch would be advisory at the only place
    anyone checks a card.
    """

    def test_a_token_minted_while_the_type_issued_cards_stops_working(self, client, db):
        _ensure_org(db)
        admin = _create_admin(db, email="stale-admin@examplee6e3b1.com")
        user, member = _create_member_user(
            db, email="stale@examplee6e3b1.com", type_name="WasFull", issues_card=True
        )
        token = sign_card_token(member.id)
        client.cookies.update(_auth_cookie(admin))

        # Verifies while the type still issues cards.
        assert client.post("/api/v1/card/scan", json={"token": token}).status_code == 200

        member.membership_type.issues_card = False
        db.flush()

        response = client.post("/api/v1/card/scan", json={"token": token})

        assert response.status_code == 410, (
            "a QR captured before the switch was turned off still verified at "
            "the door, so the switch is advisory"
        )

    def test_it_is_told_apart_from_an_unknown_member_and_a_forged_code(
        self, client, db
    ):
        """Three different facts at the door, three different answers. A stale
        card reported as "member not found" would send someone looking for a
        missing record instead of a lapsed tier."""
        _ensure_org(db)
        admin = _create_admin(db, email="stale-codes@examplee6e3b1.com")
        _, member = _create_member_user(
            db, email="stale-codes-m@examplee6e3b1.com",
            type_name="NoCards", issues_card=False,
        )
        client.cookies.update(_auth_cookie(admin))

        stale = client.post(
            "/api/v1/card/scan", json={"token": sign_card_token(member.id)}
        )
        unknown = client.post(
            "/api/v1/card/scan", json={"token": sign_card_token(999999)}
        )
        forged = client.post("/api/v1/card/scan", json={"token": "not-a-real-token"})

        assert stale.status_code == 410
        assert unknown.status_code == 404
        assert forged.status_code == 400


class TestThePortalIsToldWhetherToOfferTheCard:
    """`/auth/me` carries `has_member_card`, which is what the navigation and
    the route guard read.

    It exists so the portal does not have to probe `/me/card` — an endpoint
    whose job is to answer 404 — to decide whether to render a menu item. It
    folds in **both** levels, because the frontend recombining them would be a
    third place for the two-level rule to drift.
    """

    def test_it_is_true_when_the_flag_and_the_type_both_allow_it(self, client, db):
        _ensure_org(db)
        user, _ = _create_member_user(
            db, email="me-card-on@examplee6e3b1.com", type_name="Full", issues_card=True
        )
        client.cookies.update(_auth_cookie(user))

        assert client.get("/api/v1/auth/me").json()["has_member_card"] is True

    def test_it_is_false_when_the_type_does_not_issue_one(self, client, db):
        _ensure_org(db)
        user, _ = _create_member_user(
            db, email="me-card-type@examplee6e3b1.com",
            type_name="Friends2", issues_card=False,
        )
        client.cookies.update(_auth_cookie(user))

        assert client.get("/api/v1/auth/me").json()["has_member_card"] is False

    def test_it_is_false_when_the_instance_flag_is_off(self, client, db):
        """The level above. A type with the switch on must not advertise a card
        on an instance where the module does not exist."""
        _ensure_org(db, member_card=False)
        user, _ = _create_member_user(
            db, email="me-card-flag@examplee6e3b1.com", type_name="Full", issues_card=True
        )
        client.cookies.update(_auth_cookie(user))

        assert client.get("/api/v1/auth/me").json()["has_member_card"] is False

    def test_it_is_false_for_a_staff_account_with_no_member_record(self, client, db):
        """A super admin administering the club is not a member of it, so there
        is no type to consult and no card to offer."""
        _ensure_org(db)
        admin = _create_admin(db, email="me-card-staff@examplee6e3b1.com")
        client.cookies.update(_auth_cookie(admin))

        assert client.get("/api/v1/auth/me").json()["has_member_card"] is False
