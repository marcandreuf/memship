"""Club-data reset and the setup helpers that survive it.

The reset is the one destructive operation in the product, so what it *keeps*
matters more than what it deletes: the operator's own account, the system roles,
and the payment provider credentials that live in the database rather than in
`.env` — the whole reason this exists instead of "delete the postgres volume".
"""

import argparse

import pytest

from app.cli import reset as reset_module
from app.cli.reset import KNOWN_TABLES, preview_club_data, reset_club_data
from app.cli.seed import (
    DEMO_ORG,
    _run_unattended,
    any_admin_user_id,
    create_org_settings,
    create_user_with_member,
    restore_member_records,
    seed_address_types,
    seed_contact_types,
    seed_demo_org_settings,
    seed_groups,
    seed_membership_types,
    seed_narrow_role,
    set_password,
    super_admin_users,
)
from app.core.permissions import MEMBER_SLUG, SUPER_ADMIN_SLUG
from app.db.base import Base
from app.domains.audit.models import AuditLog
from app.domains.auth.models import Role, User
from app.domains.billing.models import PaymentProvider
from app.domains.members.models import Member
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person


def _base_install(db):
    seed_address_types(db)
    seed_contact_types(db)
    return seed_membership_types(db, seed_groups(db))


def _args(**overrides):
    """The parsed flags `_run_unattended` reads, defaulted to off."""
    defaults = {"reset_club_data": False, "admin_email": None, "club_name": None, "demo": False}
    return argparse.Namespace(**{**defaults, **overrides})


def _account(email, role, membership_type, db):
    create_user_with_member(
        db,
        {
            "first_name": "Test",
            "last_name": "Person",
            "email": email,
            "password": "correct horse battery staple",
        },
        role,
        membership_type,
    )
    return db.query(User).filter_by(email=email).one()


class TestTableClassification:
    def test_every_mapped_table_is_known(self):
        """A model added later must be classified deliberately.

        The failure mode this guards is silent: an unclassified table is cleared
        by default, so a second credential store would be wiped by a reset the
        same way deleting the volume wipes it.
        """
        unknown = set(Base.metadata.tables) - KNOWN_TABLES
        assert not unknown, (
            f"unclassified tables: {sorted(unknown)} — add them to KNOWN_TABLES, "
            "and to PRESERVED_TABLES/ACCOUNT_SCOPED_PREDICATES if a reset must keep them"
        )

    def test_preserved_and_account_scoped_tables_exist(self):
        """Guards against a rename leaving a stale entry that silently stops applying."""
        live = set(Base.metadata.tables)
        assert reset_module.PRESERVED_TABLES <= live
        assert set(reset_module.ACCOUNT_SCOPED_PREDICATES) <= live


class TestResetKeeps:
    def test_super_admin_account_survives(self, db):
        membership_type = _base_install(db)
        seed_demo_org_settings(db)
        keeper = _account("owner@example.org", "super_admin", membership_type, db)
        _account("club@example.org", "admin", membership_type, db)
        keeper_person_id = keeper.person_id

        reset_club_data(db)

        remaining = db.query(User).all()
        assert [u.email for u in remaining] == ["owner@example.org"]
        assert db.query(Person).filter_by(id=keeper_person_id).one_or_none() is not None

    def test_payment_provider_credentials_survive(self, db):
        membership_type = _base_install(db)
        _account("owner@example.org", "super_admin", membership_type, db)
        db.add(
            PaymentProvider(
                provider_type="stripe",
                display_name="Stripe",
                status="active",
                config={"secret_key": "sk_live_kept"},
            )
        )
        db.flush()

        reset_club_data(db)

        provider = db.query(PaymentProvider).one()
        assert provider.config["secret_key"] == "sk_live_kept"

    def test_system_roles_survive_and_custom_roles_do_not(self, db):
        membership_type = _base_install(db)
        _account("owner@example.org", "super_admin", membership_type, db)
        seed_narrow_role(db)
        assert db.query(Role).filter_by(slug="treasurer").one_or_none() is not None

        reset_club_data(db)

        slugs = {r.slug for r in db.query(Role).all()}
        assert {"super_admin", "admin", "member"} <= slugs
        assert "treasurer" not in slugs

    def test_system_role_permissions_survive(self, db):
        membership_type = _base_install(db)
        _account("owner@example.org", "super_admin", membership_type, db)
        # `admin`, not `super_admin`: the super admin bypasses permission checks
        # by slug (app/core/authorization.py) and holds no explicit grants.
        before = len(db.query(Role).filter_by(slug="admin").one().permissions)
        assert before > 0

        reset_club_data(db)

        after = len(db.query(Role).filter_by(slug="admin").one().permissions)
        assert after == before


class TestResetClears:
    def test_club_data_and_organization_go(self, db):
        membership_type = _base_install(db)
        seed_demo_org_settings(db)
        _account("owner@example.org", "super_admin", membership_type, db)
        _account("member@example.org", "member", membership_type, db)

        reset_club_data(db)

        assert db.query(OrganizationSettings).count() == 0
        # Only the super admin's own record would come back, and only via
        # restore_member_records — the reset itself leaves none.
        assert db.query(Member).count() == 0

    def test_preview_matches_what_is_deleted(self, db):
        membership_type = _base_install(db)
        seed_demo_org_settings(db)
        _account("owner@example.org", "super_admin", membership_type, db)
        _account("member@example.org", "member", membership_type, db)

        predicted = preview_club_data(db)
        deleted = reset_club_data(db)

        assert predicted == deleted

    def test_reset_is_idempotent(self, db):
        membership_type = _base_install(db)
        _account("owner@example.org", "super_admin", membership_type, db)

        reset_club_data(db)
        second = reset_club_data(db)

        assert second == {}

    def test_survivors_get_their_member_record_back(self, db):
        membership_type = _base_install(db)
        keeper = _account("owner@example.org", "super_admin", membership_type, db)

        reset_club_data(db)
        membership_type = seed_membership_types(db, seed_groups(db))
        restore_member_records(db, super_admin_users(db), membership_type)

        member = db.query(Member).filter_by(person_id=keeper.person_id).one()
        assert member.user_id == keeper.id
        assert member.status == "active"


class TestCreatedByResolution:
    def test_resolves_by_role_not_by_address(self, db):
        """The `--demo` layer used to look up a literal `admin@test.com`.

        Applied on top of an operator-chosen super admin that returned None
        silently, and every demo record was stamped with no creator.
        """
        membership_type = _base_install(db)
        owner = _account("owner@example.org", "super_admin", membership_type, db)

        assert db.query(User).filter_by(email="admin@test.com").first() is None
        assert any_admin_user_id(db) == owner.id

    def test_returns_none_when_no_admin_exists(self, db):
        _base_install(db)
        assert any_admin_user_id(db) is None


class TestOrganizationDetails:
    def test_real_club_gets_only_what_was_entered(self, db):
        """The fake tax ID and IBAN are demo data, not install defaults."""
        _base_install(db)
        create_org_settings(db, {"name": "Agrupació Excursionista", "email": "hola@ae.example"})

        org = db.query(OrganizationSettings).one()
        assert org.name == "Agrupació Excursionista"
        assert org.email == "hola@ae.example"
        assert org.tax_id is None
        assert org.bank_iban is None
        assert org.legal_name is None

    def test_demo_club_gets_the_full_sample(self, db):
        _base_install(db)
        seed_demo_org_settings(db)

        org = db.query(OrganizationSettings).one()
        assert org.name == DEMO_ORG["name"]
        assert org.bank_iban == DEMO_ORG["bank_iban"]

    def test_second_call_leaves_the_existing_organization_alone(self, db):
        _base_install(db)
        create_org_settings(db, {"name": "First"})
        create_org_settings(db, {"name": "Second"})

        assert db.query(OrganizationSettings).one().name == "First"


class TestPasswordRecovery:
    """The host-side recovery path — the only one a super admin has.

    The web flow refuses them (see `domains/auth/service.request_password_reset`),
    so these are not a convenience: they are how an operator gets back into an
    instance whose SMTP was never configured.
    """

    def test_reset_is_recorded_in_the_audit_log(self, db):
        membership_type = _base_install(db)
        user = _account("owner@test.com", SUPER_ADMIN_SLUG, membership_type, db)

        set_password(db, user, "a whole new password")

        entry = (
            db.query(AuditLog)
            .filter(AuditLog.table_name == "users", AuditLog.record_id == user.id)
            .one()
        )
        assert entry.action == "update"
        assert entry.changed_fields == ["password_hash"]
        # Nobody was signed in — the actor was whoever holds shell on the host.
        assert entry.user_id is None
        assert entry.user_agent == "app.cli.seed"

    def test_unattended_resets_a_super_admin(self, db, monkeypatch):
        membership_type = _base_install(db)
        user = _account("owner@test.com", SUPER_ADMIN_SLUG, membership_type, db)
        before = user.password_hash
        monkeypatch.setenv("MEMSHIP_ADMIN_PASSWORD", "a whole new password")

        _run_unattended(db, membership_type, _args(admin_email="owner@test.com"))

        assert user.password_hash != before

    def test_unattended_refuses_an_address_that_is_not_a_super_admin(self, db, monkeypatch):
        """The flag would otherwise reset a stranger and report a super admin.

        `--admin-email` on an ordinary member's address used to reset that
        member's password, print "super admin: password reset", and not grant
        the role — handing out somebody else's credentials while doing neither
        of the two things the output claimed.
        """
        membership_type = _base_install(db)
        member = _account("member@test.com", MEMBER_SLUG, membership_type, db)
        before = member.password_hash
        monkeypatch.setenv("MEMSHIP_ADMIN_PASSWORD", "a whole new password")

        with pytest.raises(SystemExit):
            _run_unattended(db, membership_type, _args(admin_email="member@test.com"))

        assert member.password_hash == before


class TestUnknownTableGuard:
    def test_reset_refuses_when_a_table_is_unclassified(self, db, monkeypatch):
        monkeypatch.setattr(reset_module, "KNOWN_TABLES", frozenset({"users"}))
        with pytest.raises(RuntimeError, match="does not know what to do"):
            reset_club_data(db)
