from dataclasses import dataclass, field

import pytest

from app.core.authorization import is_staff, resolve_permissions
from app.core.permissions import (
    ADMIN_SEED_KEYS,
    ALL_KEYS,
    CATALOG,
    MEMBER_SEED_KEYS,
    RESERVED_KEYS,
    SELF_KEYS,
    assignable_to_custom_role,
    is_valid,
    unknown_keys,
)


@dataclass
class FakeRole:
    slug: str
    permission_keys: set[str] = field(default_factory=set)


@dataclass
class FakeUser:
    roles: list[FakeRole] = field(default_factory=list)


class TestResolvePermissions:
    def test_super_admin_resolves_to_whole_catalog_not_empty_set(self):
        """The rows are deliberately empty; an empty result would break every
        subset and "holds any" check downstream."""
        user = FakeUser(roles=[FakeRole(slug="super_admin")])

        assert resolve_permissions(user) == ALL_KEYS
        assert RESERVED_KEYS <= resolve_permissions(user)

    def test_super_admin_wins_even_when_combined_with_narrow_roles(self):
        user = FakeUser(
            roles=[
                FakeRole(slug="treasurer", permission_keys={"billing.read"}),
                FakeRole(slug="super_admin"),
            ]
        )

        assert resolve_permissions(user) == ALL_KEYS

    def test_multiple_roles_union(self):
        user = FakeUser(
            roles=[
                FakeRole(slug="member", permission_keys=set(MEMBER_SEED_KEYS)),
                FakeRole(slug="treasurer", permission_keys={"billing.read", "billing.write"}),
            ]
        )

        held = resolve_permissions(user)

        assert "billing.write" in held
        assert SELF_KEYS <= held

    def test_keys_outside_the_catalog_are_ignored(self):
        user = FakeUser(
            roles=[FakeRole(slug="stale", permission_keys={"billing.read", "billing.teleport"})]
        )

        assert resolve_permissions(user) == {"billing.read"}

    def test_no_roles_resolves_to_nothing(self):
        assert resolve_permissions(FakeUser()) == frozenset()


class TestIsStaff:
    def test_self_only_account_is_not_staff(self):
        assert not is_staff(frozenset(MEMBER_SEED_KEYS))

    def test_super_admin_is_staff(self):
        user = FakeUser(roles=[FakeRole(slug="super_admin")])

        assert is_staff(resolve_permissions(user))

    def test_one_administrative_key_is_enough(self):
        assert is_staff(frozenset(SELF_KEYS | {"members.read"}))


class TestCatalog:
    def test_keys_are_unique(self):
        keys = [p.key for p in CATALOG]

        assert len(keys) == len(set(keys))

    def test_reserved_keys_are_exactly_the_two_super_admin_only_ones(self):
        assert RESERVED_KEYS == {"roles.write", "settings.integrations.write"}

    def test_admin_seed_withholds_reserved_and_custom_field_definitions(self):
        """Parity with the pre-v1.4 hierarchy: all three are super-admin-only today."""
        assert not (ADMIN_SEED_KEYS & RESERVED_KEYS)
        assert "settings.custom_fields.write" not in ADMIN_SEED_KEYS

    def test_admin_seed_holds_every_action_permission(self):
        for key in ("activities.publish", "communications.send", "billing.run", "members.approve"):
            assert key in ADMIN_SEED_KEYS

    def test_member_seed_is_exactly_the_self_namespace(self):
        assert MEMBER_SEED_KEYS == SELF_KEYS
        assert all(key.startswith("self.") for key in MEMBER_SEED_KEYS)

    def test_self_keys_are_disjoint_from_administrative_keys(self):
        administrative = ALL_KEYS - SELF_KEYS

        assert not any(key.startswith("self.") for key in administrative)

    @pytest.mark.parametrize(
        "key,domain,action",
        [
            ("members.read", "members", "read"),
            ("settings.custom_fields.write", "settings.custom_fields", "write"),
            ("self.profile.read", "self.profile", "read"),
        ],
    )
    def test_domain_and_action_split_on_the_last_dot(self, key, domain, action):
        permission = next(p for p in CATALOG if p.key == key)

        assert (permission.domain, permission.action) == (domain, action)

    def test_i18n_keys_derive_from_the_permission_key(self):
        permission = next(p for p in CATALOG if p.key == "billing.run")

        assert permission.label_key == "permissions.billing.run.label"
        assert permission.description_key == "permissions.billing.run.description"

    def test_validation_helpers(self):
        assert is_valid("members.read")
        assert not is_valid("members.teleport")
        assert unknown_keys({"members.read", "nope"}) == {"nope"}
        assert assignable_to_custom_role({"billing.read"})
        assert not assignable_to_custom_role({"billing.read", "roles.write"})
