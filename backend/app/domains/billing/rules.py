"""The billing and reminder values an organization configures in ``features``.

The counterpart of ``domains/bookings/rules.py`` for this domain, sharing its
machinery through ``domains/shared/feature_rules.py``.

These four had no protection at either end (#493). Nothing refused a wrong type
on save, and every read was a bare ``features.get(key, default)``, so a string or
a null flowed straight into arithmetic. For the three reminder values that failed
the scheduled dunning run: ``reminders_due`` compares ``len(sent) >= max_count``
and adds ``timedelta(days=days_after_due)`` to a due date.

The failure was **dormant until there was something to remind about**, because the
comparison sits inside the loop over overdue candidates. An instance holding a bad
value and no overdue receipts ran clean every night; the first receipt to go
overdue broke the task, a long way in time from whatever wrote the value.
"""

from app.domains.shared.feature_rules import (
    IntRules,
    int_rule,
    validate_bool_keys,
    validate_email_keys,
    validate_int_rules,
)

#: key -> (default, minimum, maximum). Each bound is chosen so that no value a
#: real instance could plausibly hold changes meaning when the read-side
#: fallback starts applying. See the note in ``shared/feature_rules.py``.
INT_RULES: IntRules = {
    # Days after the due date before the first reminder. 0 is accepted: it means
    # "on the due date", which is a legitimate choice. The year bound mirrors
    # `booking_window_days`, and it feeds `timedelta`.
    "reminder_days_after_due": (3, 0, 365),
    # Days between reminders. 0 is accepted rather than refused, because the
    # "one reminder per receipt per day" guard in `reminders_due` already bounds
    # what 0 can do, and refusing it would make the read-side fallback change
    # behaviour on an instance that had stored it.
    "reminder_repeat_days": (7, 0, 365),
    # How many reminders a receipt may receive in total. 0 is accepted for the
    # same reason: it means "send none", which duplicates
    # `payment_reminders_enabled` but is harmless and is honoured today.
    "reminder_max_count": (3, 0, 100),
    # Day of the month to bill on. The maximum is 31, not 28: `is_frequency_due`
    # resolves it through `effective_billing_day`, which pulls a 29/30/31 back to
    # the last day of a short month, and whose docstring calls those "a
    # reasonable month-end choice". Capping lower would break a configuration the
    # product supports on purpose. The gap here was never the range, since
    # `max(billing_day, 1)` already clamped it, but the type: `max("x", 1)`
    # raises.
    "recurring_billing_day": (1, 1, 31),
    # The bounds on a member-initiated donation, in whole units of the org's
    # currency. Both are configured rather than fixed in code because the
    # sensible ceiling for a village club and for a professional association
    # differ by two orders of magnitude (#434).
    #
    # The minimum also drives the suggested amounts, so it is the one knob that
    # shapes the page: see ``suggested_donation_amounts``. A minimum above zero
    # is the point of it, which is why 0 is refused here where the reminder
    # values accept it.
    "donation_min_amount": (5, 1, 100_000),
    # 100.000 is the widest any instance could want and still be a donation
    # rather than a transfer its bank will ask about. It bounds the *setting*;
    # what stops a typo at the keyboard is the per-donation check against
    # whatever this is set to.
    "donation_max_amount": (1_000, 1, 100_000),
}


#: Validated on save, but **not** read through ``billing_int_rule``. Both reads
#: already coerce with ``int()`` inside a ``try`` and clamp with ``max(0, ...)``,
#: so neither can raise, and ``int()`` accepts a numeric string: ``"5"`` reads as
#: 5 today. Routing them through the registry above would reject that string and
#: fall back to the default instead, which reinterprets a value an instance has
#: already stored. Refusing it on the way in costs nothing, because no stored
#: value is re-read.
#:
#: Only the bounds are live here. The default in each tuple is never read,
#: because nothing resolves these keys through the registry, and it is a literal
#: rather than the service's own constant because importing
#: ``recurring_billing_service`` from here would close an import cycle. So the
#: two can drift without consequence; if that ever stops being true, move the
#: constants down here and let the services import them instead.
SAVE_ONLY_INT_RULES: IntRules = {
    # Days after emission before a membership fee is due. Mirrors
    # `recurring_billing_service.DEFAULT_MEMBERSHIP_FEE_DUE_DAYS`, which is 7.
    "membership_fee_due_days": (7, 0, 365),
    # Days past due before an unpaid member loses their tier. Mirrors
    # `lapse_service.DEFAULT_GRACE_DAYS`, which is 21.
    "membership_lapse_grace_days": (21, 0, 365),
}

#: Flags this domain reads as booleans. `payment_reminders_enabled` and
#: `recurring_billing_enabled` are read for truthiness and
#: `membership_lapse_enabled` through `bool()`, so none of them can raise. What
#: the check buys is the string `"false"` reading as on.
BOOL_KEYS = frozenset(
    {
        "payment_reminders_enabled",
        "recurring_billing_enabled",
        "membership_lapse_enabled",
        # The gate on the member-facing donate page. A module gate in every way
        # that matters — absent means off, and the endpoints answer 404 — but it
        # is declared here rather than in ``MODULE_GATE_KEYS`` because this
        # domain has a ``rules.py`` and owns the two values beside it.
        "member_donations_enabled",
    }
)


#: Addresses this domain stores in ``features``. The notification address was
#: the one address the product stored without validating, so a typo in it meant
#: the billing summary silently never arrived: the send is deliberately
#: best-effort, so a malformed address raises nothing a user sees and the only
#: record is a log line nobody reads until they are already looking (#495).
#:
#: Save-side only, like the booleans. A read-side fallback is not available
#: here: there is no default address to fall back *to*, and silently not
#: sending is what the defect already does.
EMAIL_KEYS = frozenset({"billing_notification_email"})

#: Every key this domain owns, for the canonical set in
#: ``domains/organizations/feature_keys.py`` (#494). This domain has no module
#: gate: billing is not optional on an instance.
FEATURE_KEYS = (
    frozenset(INT_RULES) | frozenset(SAVE_ONLY_INT_RULES) | BOOL_KEYS | EMAIL_KEYS
)


def validate_donation_bounds(features: dict) -> dict:
    """Refuse a maximum below the minimum, when one request carries both.

    Deliberately partial. ``PUT /settings/`` merges *after* the schema runs, so
    a request setting only the maximum cannot be compared against a minimum
    that is still only in the row. Rather than read the database from a
    validator, the read side resolves the pair itself and never trusts the
    stored order (see ``donation_amount_bounds``); this check exists for the
    case the settings form actually produces, which submits both together, so
    an administrator is told at the keyboard instead of silently having the
    narrower pair applied.

    Runs after ``validate_int_rules``, which has already refused a non-integer
    in either key, so the comparison cannot raise on a type.
    """
    lo, hi = features.get("donation_min_amount"), features.get("donation_max_amount")
    if lo is not None and hi is not None and hi < lo:
        raise ValueError("donation_max_amount must not be below donation_min_amount")
    return features


def validate_billing_rules(features: dict) -> dict:
    validate_int_rules(features, INT_RULES)
    validate_int_rules(features, SAVE_ONLY_INT_RULES)
    validate_bool_keys(features, BOOL_KEYS)
    validate_donation_bounds(features)
    return validate_email_keys(features, EMAIL_KEYS)


def billing_int_rule(features: dict, key: str) -> int:
    return int_rule(features, key, INT_RULES)
