"""The permission catalog.

Defined in code, never in a table: adding a permission is a code change plus a
seed update, and `role_permissions` stores validated keys as plain strings.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Permission:
    key: str
    domain: str
    action: str
    reserved: bool

    @property
    def label_key(self) -> str:
        return f"permissions.{self.key}.label"

    @property
    def description_key(self) -> str:
        return f"permissions.{self.key}.description"


def _p(key: str, *, reserved: bool = False) -> Permission:
    domain, _, action = key.rpartition(".")
    return Permission(key=key, domain=domain, action=action, reserved=reserved)


ADMINISTRATIVE: tuple[Permission, ...] = (
    _p("members.read"),
    _p("members.write"),
    _p("members.approve"),
    _p("membership.read"),
    _p("membership.write"),
    _p("activities.read"),
    _p("activities.write"),
    _p("activities.publish"),
    _p("registrations.read"),
    _p("registrations.write"),
    _p("billing.read"),
    _p("billing.write"),
    _p("billing.run"),
    _p("communications.read"),
    _p("communications.write"),
    _p("communications.send"),
    _p("bookings.read"),
    _p("bookings.write"),
    _p("reports.read"),
    _p("reminders.read"),
    _p("reminders.write"),
    _p("settings.read"),
    _p("settings.write"),
    _p("settings.custom_fields.write"),
    _p("settings.integrations.write", reserved=True),
    _p("users.read"),
    _p("users.write"),
    _p("roles.read"),
    _p("roles.write", reserved=True),
)

SELF_SERVICE: tuple[Permission, ...] = (
    _p("self.profile.read"),
    _p("self.profile.write"),
    _p("self.activities.read"),
    _p("self.registrations.read"),
    _p("self.registrations.write"),
    _p("self.billing.read"),
    _p("self.billing.write"),
    _p("self.card.read"),
    _p("self.bookings.read"),
    _p("self.bookings.write"),
    _p("self.communications.read"),
    _p("self.communications.write"),
)

CATALOG: tuple[Permission, ...] = ADMINISTRATIVE + SELF_SERVICE

BY_KEY: dict[str, Permission] = {p.key: p for p in CATALOG}

ALL_KEYS: frozenset[str] = frozenset(BY_KEY)

SELF_KEYS: frozenset[str] = frozenset(p.key for p in SELF_SERVICE)

# Rejected on any non-system role, so only super_admin ever holds them. This is
# what makes "only the superadmin authors roles / touches credentials" a property
# of the model rather than a convention.
RESERVED_KEYS: frozenset[str] = frozenset(p.key for p in CATALOG if p.reserved)

SUPER_ADMIN_SLUG = "super_admin"
ADMIN_SLUG = "admin"
MEMBER_SLUG = "member"

# Parity with the pre-v1.4 hierarchy: today's admin cannot edit custom-field
# definitions (super-admin only), so seeding it here would be a privilege grant
# disguised as a migration.
ADMIN_SEED_KEYS: frozenset[str] = ALL_KEYS - RESERVED_KEYS - {"settings.custom_fields.write"}

MEMBER_SEED_KEYS: frozenset[str] = SELF_KEYS


def is_valid(key: str) -> bool:
    return key in BY_KEY


def assignable_to_custom_role(keys: set[str]) -> bool:
    return not (keys & RESERVED_KEYS)


def unknown_keys(keys: set[str]) -> set[str]:
    return keys - ALL_KEYS


def grouped_by_domain() -> dict[str, list[Permission]]:
    grouped: dict[str, list[Permission]] = {}
    for permission in CATALOG:
        grouped.setdefault(permission.domain, []).append(permission)
    return grouped
