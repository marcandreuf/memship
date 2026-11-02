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

from app.domains.shared.feature_rules import IntRules, int_rule, validate_int_rules

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
}


def validate_billing_rules(features: dict) -> dict:
    return validate_int_rules(features, INT_RULES)


def billing_int_rule(features: dict, key: str) -> int:
    return int_rule(features, key, INT_RULES)
