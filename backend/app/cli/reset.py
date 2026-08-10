"""Club-data reset — return an instance to a clean state without losing the
operator's own account or the instance-level configuration.

Deleting the database volume is not a substitute. Payment provider credentials
live in ``payment_providers.config`` (encrypted with the Fernet key), not in
``.env``, so wiping the volume forces the operator to re-enter every secret they
configured while evaluating. This clears the club and keeps the instance.

What survives a reset:

- the super admin accounts, and the people records behind them
- the system roles and their permission grants
- the address/contact type lookups
- ``payment_providers``

Everything else is club data and goes, including custom roles, which are
authored by the club rather than shipped with the product.
"""

from sqlalchemy import bindparam, text

from app.core.permissions import SUPER_ADMIN_SLUG
from app.db import models_registry  # noqa: F401  — populates Base.metadata
from app.db.base import Base

# Every table this module knew about when it was written. Checked against the
# live metadata before anything is deleted: a table added later is a decision
# somebody has to make, not something to guess at. Getting it wrong in the
# silent direction means a reset leaves club data behind, or wipes a second
# credential store the way a volume wipe would.
KNOWN_TABLES = frozenset({
    "activities", "activity_attachment_types", "activity_consents",
    "activity_modalities", "activity_prices", "addresses", "address_types",
    "announcement_recipients", "announcements", "audit_logs", "billing_runs",
    "bookings", "concepts", "contacts", "contact_types",
    "custom_field_definitions", "custom_field_values", "discount_codes",
    "groups", "members", "membership_types", "notifications",
    "organization_settings", "payment_providers", "persons",
    "receipt_reminders", "receipts", "registration_attachments",
    "registration_consents", "registrations", "reminders", "remittances",
    "role_permissions", "roles", "sepa_mandates", "spaces", "space_slots",
    "user_identities", "user_roles", "users", "webhook_events",
})

# Instance-level configuration and lookups. A club reset never touches these.
PRESERVED_TABLES = frozenset({
    "address_types",
    "contact_types",
    # The reason this command exists instead of "delete the postgres volume".
    "payment_providers",
    # Cleared transitively: role_permissions.role_id is ON DELETE CASCADE, so
    # dropping the custom roles takes their grants with them while the system
    # roles keep theirs.
    "role_permissions",
})

# Rows belonging to the surviving operator accounts stay; the rest go. Keyed by
# table, valued by the WHERE clause that spares them. `:user_ids` and
# `:person_ids` are bound as expanding lists.
ACCOUNT_SCOPED_PREDICATES = {
    "users": "id NOT IN :user_ids",
    "persons": "id NOT IN :person_ids",
    "user_roles": "user_id NOT IN :user_ids",
    "user_identities": "user_id NOT IN :user_ids",
    # Custom roles are club data. The system roles are the product.
    "roles": "is_system = false",
}


def _check_metadata_is_classified() -> None:
    live = set(Base.metadata.tables)
    unknown = live - KNOWN_TABLES
    if unknown:
        raise RuntimeError(
            "app/cli/reset.py does not know what to do with these tables: "
            + ", ".join(sorted(unknown))
            + ". Add each one to KNOWN_TABLES, and to PRESERVED_TABLES or "
            "ACCOUNT_SCOPED_PREDICATES if a club reset must not clear it."
        )


def _preserved_ids(db) -> tuple[list[int], list[int]]:
    """User and person ids for the super admins, who outlive a reset."""
    rows = db.execute(
        text(
            "SELECT u.id, u.person_id FROM users u "
            "JOIN user_roles ur ON ur.user_id = u.id "
            "JOIN roles r ON r.id = ur.role_id "
            "WHERE r.slug = :slug"
        ),
        {"slug": SUPER_ADMIN_SLUG},
    ).all()
    return [r[0] for r in rows], [r[1] for r in rows]


def _where(table_name: str, user_ids: list[int], person_ids: list[int]) -> tuple[str, dict]:
    """The WHERE clause sparing the preserved rows, and its parameters.

    Returns an empty clause when the whole table goes — either because it holds
    no preserved rows, or because there is nothing to preserve.
    """
    predicate = ACCOUNT_SCOPED_PREDICATES.get(table_name)
    if predicate is None:
        return "", {}

    params: dict[str, list[int]] = {}
    if "user_ids" in predicate:
        # `NOT IN ()` is a syntax error, and with nothing to spare the predicate
        # is vacuous anyway — clear the table.
        if not user_ids:
            return "", {}
        params["user_ids"] = user_ids
    if "person_ids" in predicate:
        if not person_ids:
            return "", {}
        params["person_ids"] = person_ids
    return f" WHERE {predicate}", params


def _statement(sql: str, params: dict):
    """A text() with every list parameter bound as expanding."""
    stmt = text(sql)
    for name in params:
        stmt = stmt.bindparams(bindparam(name, expanding=True))
    return stmt


def preview_club_data(db) -> dict[str, int]:
    """Row counts a reset would delete, per table. Only non-empty tables."""
    _check_metadata_is_classified()
    user_ids, person_ids = _preserved_ids(db)

    counts: dict[str, int] = {}
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in PRESERVED_TABLES:
            continue
        where, params = _where(table.name, user_ids, person_ids)
        stmt = _statement(f"SELECT count(*) FROM {table.name}{where}", params)
        count = db.execute(stmt, params).scalar_one()
        if count:
            counts[table.name] = count
    return counts


def reset_club_data(db) -> dict[str, int]:
    """Delete every club-scoped row. Returns what was removed, per table.

    Does not commit — the caller owns the transaction, so a failure part-way
    through leaves the instance exactly as it was.
    """
    _check_metadata_is_classified()
    user_ids, person_ids = _preserved_ids(db)

    deleted: dict[str, int] = {}
    # Dependency order, children first, so plain DELETEs never trip a foreign
    # key and nothing needs CASCADE — which on a TRUNCATE would happily follow
    # the references back into `users` and delete the operator too.
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in PRESERVED_TABLES:
            continue
        where, params = _where(table.name, user_ids, person_ids)
        result = db.execute(_statement(f"DELETE FROM {table.name}{where}", params), params)
        if result.rowcount:
            deleted[table.name] = result.rowcount

    # The deletes went out as SQL, so the session's identity map still holds the
    # objects they removed. Without this, re-creating the organization — same
    # `id = 1`, since the table is single-row — collides with the stale instance
    # and SQLAlchemy warns about a duplicate identity key.
    db.expire_all()
    return deleted
