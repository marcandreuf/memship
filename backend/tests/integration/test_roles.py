import pytest

from app.core.authorization import is_staff, resolve_permissions
from app.core.permissions import ADMIN_SEED_KEYS, ALL_KEYS, MEMBER_SEED_KEYS, RESERVED_KEYS
from app.domains.auth.models import Role, User, UserRoleAssignment
from app.domains.auth.roles import assign_roles
from app.domains.persons.models import Person


def _user(db, email, role="member"):
    person = Person(first_name="Role", last_name="Tester", email=email)
    db.add(person)
    db.flush()
    user = User(person_id=person.id, email=email, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.flush()
    return user


class TestSeededSystemRoles:
    def test_the_three_system_roles_exist(self, db):
        slugs = {r.slug for r in db.query(Role).filter(Role.is_system.is_(True)).all()}

        assert {"super_admin", "admin", "member"} <= slugs

    def test_super_admin_stores_no_permission_rows(self, db):
        role = db.query(Role).filter_by(slug="super_admin").one()

        assert role.permission_keys == set()

    def test_admin_and_member_store_their_seed_sets(self, db):
        admin = db.query(Role).filter_by(slug="admin").one()
        member = db.query(Role).filter_by(slug="member").one()

        assert admin.permission_keys == set(ADMIN_SEED_KEYS)
        assert member.permission_keys == set(MEMBER_SEED_KEYS)


class TestResolutionAgainstTheDatabase:
    def test_super_admin_resolves_to_the_whole_catalog(self, db):
        user = _user(db, "super-roles@examplee6e3b1.com", role="super_admin")

        assert resolve_permissions(user) == ALL_KEYS
        assert RESERVED_KEYS <= resolve_permissions(user)

    def test_admin_holds_the_seed_set_and_no_reserved_key(self, db):
        user = _user(db, "admin-roles@examplee6e3b1.com", role="admin")

        held = resolve_permissions(user)

        assert "members.write" in held
        assert not (held & RESERVED_KEYS)
        assert "settings.custom_fields.write" not in held

    def test_member_holds_only_the_self_namespace(self, db):
        user = _user(db, "member-roles@examplee6e3b1.com")

        held = resolve_permissions(user)

        assert held == set(MEMBER_SEED_KEYS)
        assert not is_staff(held)

    def test_every_account_holds_member(self, db):
        for email, role in (
            ("pin-super@examplee6e3b1.com", "super_admin"),
            ("pin-admin@examplee6e3b1.com", "admin"),
            ("pin-member@examplee6e3b1.com", "member"),
        ):
            user = _user(db, email, role=role)

            assert "member" in {r.slug for r in user.roles}

    def test_staff_accounts_also_hold_the_self_namespace(self, db):
        user = _user(db, "staff-self@examplee6e3b1.com", role="admin")

        assert set(MEMBER_SEED_KEYS) <= resolve_permissions(user)


class TestAssignRoles:
    def test_assigns_member_by_default(self, db):
        user = _user(db, "assign-1@examplee6e3b1.com")
        db.query(UserRoleAssignment).filter_by(user_id=user.id).delete()
        db.expire(user)

        assign_roles(db, user)
        db.flush()
        db.refresh(user)

        assert {r.slug for r in user.roles} == {"member"}

    def test_is_idempotent(self, db):
        user = _user(db, "assign-2@examplee6e3b1.com", role="admin")

        assign_roles(db, user, "admin")
        db.flush()
        db.refresh(user)

        assert sorted(r.slug for r in user.roles) == ["admin", "member"]


class TestRoleDeletionIsRestricted:
    def test_deleting_an_assigned_role_is_refused_by_the_database(self, db):
        from sqlalchemy.exc import IntegrityError

        _user(db, "restrict-del@examplee6e3b1.com", role="admin")
        admin_role = db.query(Role).filter_by(slug="admin").one()

        with pytest.raises(IntegrityError):
            db.query(Role).filter_by(id=admin_role.id).delete(synchronize_session=False)
            db.flush()
