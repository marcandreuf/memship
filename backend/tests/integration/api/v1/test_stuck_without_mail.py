"""Self-registration when the club's mail is not working, and the way back.

Sign-in requires a confirmed address, the only self-service way to confirm one
is a link sent by email, and a fresh self-hosted install has no mail provider.
So a member who registered before setup finished could never sign in, showed in
the members list as **active**, and nothing in the product could unstick them —
``/auth/resend-verification`` went through the same broken transport, and the
endpoints that look like they would help set flags that were already true
(#231).

Two halves, and both are needed: refusing the registration stops new members
getting stuck, and the rescue frees the ones who already are. Neither covers
the other.

``development`` masks all of this — ``/auth/register`` hands the token back
when there is no transport — so these tests run with ``APP_ENV`` patched to
something else. That is the environment a self-hoster is actually in.
"""

import pytest

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.audit.models import AuditLog
from app.domains.auth.models import User
from app.domains.auth.service import _issue_verification_token
from app.domains.members.models import Member, MembershipType
from app.domains.persons.models import Person

PASSWORD = "password123"


@pytest.fixture
def production(monkeypatch):
    """Anywhere that is not a developer's laptop."""
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "APP_ENV", "production")


@pytest.fixture
def no_transport(monkeypatch):
    """No mail provider configured — the state of a fresh install."""
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.mailing_enabled", lambda db: False
    )


@pytest.fixture
def working_transport(monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.mailing_enabled", lambda db: True
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.send_verification_email",
        lambda *args, **kwargs: True,
    )


def _default_tier(db):
    mt = db.query(MembershipType).filter_by(is_default=True).first()
    if not mt:
        mt = MembershipType(
            name="General", slug="general", base_price=0, is_active=True,
            is_default=True,
        )
        db.add(mt)
        db.flush()
    return mt


def _admin(db, suffix, role="admin"):
    email = f"{suffix}-{role}@example8c24d1.com"
    person = Person(first_name="Club", last_name="Admin", email=email)
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=email,
        password_hash=hash_password(PASSWORD),
        role=role,
        is_active=True,
        email_verified=True,
    )
    db.add(user)
    db.flush()
    return user


def _stuck_member(db, suffix):
    """A member who registered and never confirmed: active, and locked out.

    The token is issued through the real path rather than written as a literal.
    Tokens are stored as digests, so a literal is not a token at all and any
    test that tried to redeem one would pass without proving anything.
    """
    email = f"{suffix}@example8c24d1.com"
    person = Person(first_name="Stuck", last_name=suffix, email=email)
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=email,
        password_hash=hash_password(PASSWORD),
        role="member",
        is_active=True,
        email_verified=False,
    )
    db.add(user)
    db.flush()
    # The link that was generated and never delivered.
    user.plain_verification_token = _issue_verification_token(user)
    db.flush()
    member = Member(
        person_id=person.id,
        user_id=user.id,
        membership_type_id=_default_tier(db).id,
        member_number=f"M-{suffix}",
        status="active",
        is_active=True,
    )
    db.add(member)
    db.flush()
    return member


def _cookie(user):
    return {"access_token": create_access_token(user.id)}


class TestRegistrationIsRefusedWhenItCannotBeCompleted:
    def test_registering_without_a_transport_is_refused(
        self, client, db, production, no_transport
    ):
        _default_tier(db)
        db.commit()

        response = client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "New",
                "last_name": "User",
                "email": "refused@example8c24d1.com",
                "password": PASSWORD,
            },
        )

        assert response.status_code == 503
        assert "email" in response.json()["detail"].lower()

    def test_no_account_is_left_behind_by_the_refusal(
        self, client, db, production, no_transport
    ):
        """The door closes before anything is written. A created-then-refused
        account would be the very thing this prevents."""
        _default_tier(db)
        db.commit()
        address = "nothing-written@example8c24d1.com"

        client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "New",
                "last_name": "User",
                "email": address,
                "password": PASSWORD,
            },
        )

        assert db.query(User).filter(User.email == address).first() is None
        assert db.query(Person).filter(Person.email == address).first() is None

    def test_registering_with_a_transport_still_works(
        self, client, db, production, working_transport
    ):
        _default_tier(db)
        db.commit()

        response = client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "New",
                "last_name": "User",
                "email": "allowed@example8c24d1.com",
                "password": PASSWORD,
            },
        )

        assert response.status_code == 201

    def test_development_is_unaffected(self, client, db, no_transport):
        """No transport, but the token comes back in the response, so the
        account is reachable and registering is not a trap."""
        _default_tier(db)
        db.commit()

        response = client.post(
            "/api/v1/auth/register",
            json={
                "first_name": "Dev",
                "last_name": "User",
                "email": "dev-ok@example8c24d1.com",
                "password": PASSWORD,
            },
        )

        assert response.status_code == 201
        assert response.json()["verification_token"] is not None

    def test_resending_a_link_that_cannot_be_sent_is_refused(
        self, client, db, production, no_transport
    ):
        """It used to answer "a new link has been sent" and send nothing."""
        _stuck_member(db, "resend")
        db.commit()

        response = client.post(
            "/api/v1/auth/resend-verification",
            json={"email": "resend@example8c24d1.com"},
        )

        assert response.status_code == 503


class TestAnAdminCanFreeAStuckMember:
    def test_confirming_lets_the_member_sign_in(self, client, db):
        admin = _admin(db, "free")
        member = _stuck_member(db, "free1")
        db.commit()

        blocked = client.post(
            "/api/v1/auth/login",
            json={"email": member.person.email, "password": PASSWORD},
        )
        assert blocked.status_code == 403

        response = client.post(
            f"/api/v1/members/{member.id}/confirm-email", cookies=_cookie(admin)
        )
        assert response.status_code == 200
        assert response.json()["email_verified"] is True

        allowed = client.post(
            "/api/v1/auth/login",
            json={"email": member.person.email, "password": PASSWORD},
        )
        assert allowed.status_code == 200

    def test_the_audit_row_says_an_admin_did_it(self, client, db):
        """An admin who can confirm any address can confirm one they control,
        so the record has to distinguish this from the owner clicking a link."""
        admin = _admin(db, "audit")
        member = _stuck_member(db, "audit1")
        db.commit()
        user_id = member.user_id

        client.post(
            f"/api/v1/members/{member.id}/confirm-email", cookies=_cookie(admin)
        )

        row = (
            db.query(AuditLog)
            .filter(AuditLog.table_name == "users", AuditLog.record_id == user_id)
            .one()
        )
        assert row.user_id == admin.id
        assert row.new_values["confirmed_by"] == "admin"
        assert row.changed_fields == ["email_verified"]

    def test_the_unused_token_stops_working(self, client, db):
        """One address, one live path to the account. A link still sitting in a
        mailbox must not confirm anything afterwards."""
        admin = _admin(db, "token")
        member = _stuck_member(db, "token1")
        token = member.user.plain_verification_token
        db.commit()

        # The token is live until the admin acts — otherwise this proves
        # nothing about what confirming did to it.
        assert (
            client.post("/api/v1/auth/verify-email", json={"token": token}).status_code
            == 200
        )
        db.refresh(member.user)
        member.user.email_verified = False
        member.user.plain_verification_token = _issue_verification_token(member.user)
        token = member.user.plain_verification_token
        db.commit()

        client.post(
            f"/api/v1/members/{member.id}/confirm-email", cookies=_cookie(admin)
        )

        response = client.post("/api/v1/auth/verify-email", json={"token": token})
        assert response.status_code == 400

    def test_confirming_twice_writes_one_audit_row(self, client, db):
        admin = _admin(db, "twice")
        member = _stuck_member(db, "twice1")
        db.commit()
        user_id = member.user_id

        first = client.post(
            f"/api/v1/members/{member.id}/confirm-email", cookies=_cookie(admin)
        )
        second = client.post(
            f"/api/v1/members/{member.id}/confirm-email", cookies=_cookie(admin)
        )

        assert first.status_code == 200
        assert second.status_code == 200
        rows = (
            db.query(AuditLog)
            .filter(AuditLog.table_name == "users", AuditLog.record_id == user_id)
            .count()
        )
        assert rows == 1

    def test_a_member_with_no_account_is_a_conflict(self, client, db):
        """An admin-created member has no login, so there is nothing to
        confirm — as against a login whose address is unconfirmed."""
        admin = _admin(db, "nologin")
        person = Person(
            first_name="No", last_name="Login", email="nologin@example8c24d1.com"
        )
        db.add(person)
        db.flush()
        member = Member(
            person_id=person.id,
            membership_type_id=_default_tier(db).id,
            member_number="M-nologin",
            status="active",
            is_active=True,
        )
        db.add(member)
        db.commit()

        response = client.post(
            f"/api/v1/members/{member.id}/confirm-email", cookies=_cookie(admin)
        )
        assert response.status_code == 409

    def test_a_member_cannot_confirm_their_own_address(self, client, db):
        """Otherwise the confirmation step means nothing at all."""
        member = _stuck_member(db, "self")
        db.commit()

        response = client.post(
            f"/api/v1/members/{member.id}/confirm-email",
            cookies=_cookie(member.user),
        )
        assert response.status_code == 403

    def test_an_unknown_member_is_a_404(self, client, db):
        admin = _admin(db, "missing")
        db.commit()

        response = client.post(
            "/api/v1/members/99999999/confirm-email", cookies=_cookie(admin)
        )
        assert response.status_code == 404


class TestTheMemberRecordShowsTheState:
    def test_an_unconfirmed_member_is_visible_as_such(self, client, db):
        """The admin saw an active member who could not sign in, with nothing
        on the record saying why."""
        admin = _admin(db, "shows")
        member = _stuck_member(db, "shows1")
        db.commit()

        body = client.get(
            f"/api/v1/members/{member.id}", cookies=_cookie(admin)
        ).json()

        assert body["status"] == "active"
        assert body["email_verified"] is False

    def test_a_member_without_a_login_reports_none(self, client, db):
        admin = _admin(db, "nouser")
        person = Person(
            first_name="Desk", last_name="Only", email="desk@example8c24d1.com"
        )
        db.add(person)
        db.flush()
        member = Member(
            person_id=person.id,
            membership_type_id=_default_tier(db).id,
            member_number="M-desk",
            status="active",
            is_active=True,
        )
        db.add(member)
        db.commit()

        body = client.get(
            f"/api/v1/members/{member.id}", cookies=_cookie(admin)
        ).json()

        assert body["email_verified"] is None
