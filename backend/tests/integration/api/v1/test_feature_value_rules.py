"""The billing and reminder configuration values are guarded at both ends (#493).

Four values in ``features`` used to have no protection anywhere: nothing refused a
wrong type on save, and every read was a bare ``features.get(key, default)``. The
three reminder values flow into ``timedelta`` arithmetic and an ``int``
comparison, so a string or a null raised ``TypeError`` inside the scheduled
dunning run.

What made it worth fixing is *when* it failed. The comparison sits inside the loop
over overdue candidates, so an instance holding a bad value and no overdue
receipts ran clean every night; the first receipt to go overdue broke the task,
far in time from whatever wrote the value, and in a Celery task rather than a
request anyone was watching. ``TestTheDunningRunSurvivesAStoredBadValue`` is the
one that pins that, and it fails on the code before this change.

The save-side tests and the read-side tests are both here on purpose: either half
alone leaves the defect reachable. Validation on save does nothing about a value
already stored, and ``features`` has been free-form JSONB since the column
existed, with seeds and migrations writing to it without passing through the
schema.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.billing.models import Receipt, ReceiptReminder
from app.domains.billing.reminder_service import run_scheduled_reminders
from app.domains.billing.rules import (
    BOOL_KEYS,
    INT_RULES,
    SAVE_ONLY_INT_RULES,
    billing_int_rule,
)
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person

SUFFIX = "@example93b1f4.test"


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id)}


def _admin(db, suffix="fv-admin") -> User:
    person = Person(first_name="Value", last_name="Admin", email=f"{suffix}{SUFFIX}")
    db.add(person)
    db.flush()
    user = User(
        party_id=person.party_id,
        email=f"{suffix}{SUFFIX}",
        password_hash=hash_password("password123"),
        role="super_admin",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _org(db, features=None) -> OrganizationSettings:
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(
            id=1,
            name="Test Organization",
            locale="es",
            timezone="Europe/Madrid",
            currency="EUR",
            date_format="DD/MM/YYYY",
        )
        db.add(org)
        db.flush()
    if features is not None:
        org.features = features
    db.flush()
    return org


# (key, value, why it is invalid). One per rejection class rather than one per
# key: wrong type, a bool masquerading as a number, under the floor, over the
# ceiling.
INVALID = [
    pytest.param("reminder_days_after_due", "3", id="days-string"),
    pytest.param("reminder_days_after_due", True, id="days-bool"),
    pytest.param("reminder_days_after_due", -1, id="days-negative"),
    pytest.param("reminder_days_after_due", 366, id="days-over-a-year"),
    pytest.param("reminder_repeat_days", "weekly", id="repeat-string"),
    pytest.param("reminder_repeat_days", None, id="repeat-null"),
    pytest.param("reminder_max_count", "lots", id="count-string"),
    pytest.param("reminder_max_count", 101, id="count-over-ceiling"),
    pytest.param("recurring_billing_day", "1", id="billing-day-string"),
    pytest.param("recurring_billing_day", 0, id="billing-day-zero"),
    pytest.param("recurring_billing_day", 32, id="billing-day-impossible"),
]

# Values at the edges of what the code already honours. These must be accepted,
# because the read-side fallback replaces whatever it rejects with the default:
# refusing one of these would silently change behaviour on an instance that had
# configured it.
VALID_EDGES = [
    pytest.param("reminder_days_after_due", 0, id="days-zero-means-on-the-due-date"),
    pytest.param("reminder_repeat_days", 0, id="repeat-zero-bounded-by-one-per-day"),
    pytest.param("reminder_max_count", 0, id="count-zero-means-send-none"),
    # `effective_billing_day` pulls 29/30/31 back to the last day of a short
    # month, and its docstring calls them a reasonable month-end choice.
    pytest.param("recurring_billing_day", 31, id="billing-day-month-end"),
]


class TestInvalidValuesAreRefusedOnSave:
    @pytest.mark.parametrize("key,value", INVALID)
    def test_settings_put_refuses_the_value(self, client, db, key, value):
        _org(db, {})
        client.cookies.update(_auth_cookie(_admin(db, f"inv-{key}-{value}")))

        response = client.put("/api/v1/settings/", json={"features": {key: value}})

        assert response.status_code == 422, (
            f"settings accepted {key}={value!r} with {response.status_code}; "
            f"the value reaches date arithmetic in the dunning run, and nothing "
            f"downstream would report where it came from"
        )

    @pytest.mark.parametrize("key,value", VALID_EDGES)
    def test_settings_put_accepts_a_value_the_code_honours(self, client, db, key, value):
        """The mirror. Without it the refusals above could pass by refusing
        everything, and the read-side fallback would start overriding values a
        real instance had deliberately set."""
        _org(db, {})
        client.cookies.update(_auth_cookie(_admin(db, f"val-{key}-{value}")))

        response = client.put("/api/v1/settings/", json={"features": {key: value}})

        assert response.status_code == 200, (
            f"settings refused {key}={value!r}, which the code honours today"
        )
        assert response.json()["features"][key] == value


class TestAStoredBadValueFallsBackOnRead:
    """Save-side validation cannot reach a value that is already stored.

    `features` is free-form JSONB and has been writable since the column
    existed; seeds and migrations write to it without passing through the
    schema. So every read falls back rather than trusting what it finds.
    """

    @pytest.mark.parametrize("key", sorted(INT_RULES))
    def test_a_wrong_typed_stored_value_reads_as_the_default(self, db, key):
        default = INT_RULES[key][0]
        org = _org(db, {key: "not a number"})

        assert billing_int_rule(org.features, key) == default

    @pytest.mark.parametrize("key", sorted(INT_RULES))
    def test_an_absent_key_reads_as_the_default(self, db, key):
        """Absence is legitimate: a fresh install stores only some of these."""
        assert billing_int_rule({}, key) == INT_RULES[key][0]

    def test_a_valid_stored_value_is_honoured(self, db):
        """The control: the fallbacks above must be about the value, not the read."""
        org = _org(db, {"reminder_max_count": 7})

        assert billing_int_rule(org.features, "reminder_max_count") == 7


class TestTheDunningRunSurvivesAStoredBadValue:
    """The regression this issue was filed for. Fails before the change.

    `reminders_due` compares `len(sent) >= max_count` and adds
    `timedelta(days=days_after_due)` to a due date. Both sit inside the loop over
    overdue candidates, so the bad value only bites once a receipt is actually
    overdue.
    """

    def _already_reminded(self, db, receipt):
        """A reminder sent a while ago, so `repeat_days` is actually consulted."""
        reminder = ReceiptReminder(
            receipt_id=receipt.id,
            reminder_number=1,
            channel="email",
            status="sent",
            to_email=f"prior{SUFFIX}",
            triggered_by="scheduled",
            sent_at=datetime.now(timezone.utc) - timedelta(days=20),
        )
        db.add(reminder)
        db.flush()
        return reminder

    def _overdue_receipt(self, db, suffix="dun"):
        person = Person(
            first_name="Deudora", last_name="Morosa", email=f"{suffix}{SUFFIX}"
        )
        db.add(person)
        db.flush()
        mtype = MembershipType(
            name=f"Type {suffix}", slug=f"type-{suffix}", base_price=Decimal("50.00")
        )
        db.add(mtype)
        db.flush()
        member = Member(
            party_id=person.party_id,
            membership_type_id=mtype.id,
            member_number=f"M-{suffix}",
            status="active",
        )
        db.add(member)
        db.flush()
        today = date.today()
        receipt = Receipt(
            receipt_number=f"R-{suffix}",
            party_id=person.party_id,
            origin="membership",
            description="Membership fee",
            base_amount=Decimal("50.00"),
            vat_rate=Decimal("0.00"),
            vat_amount=Decimal("0.00"),
            total_amount=Decimal("50.00"),
            status="emitted",
            emission_date=today - timedelta(days=60),
            due_date=today - timedelta(days=30),
        )
        db.add(receipt)
        db.flush()
        return receipt

    # The suffix is passed rather than derived from the key: it reaches
    # `membership_types.slug`, whose `membership_type_slug_format` check refuses
    # the underscores every one of these flag names contains.
    @pytest.mark.parametrize(
        "bad,suffix",
        [
            pytest.param({"reminder_max_count": "lots"}, "count", id="max-count-string"),
            pytest.param({"reminder_days_after_due": None}, "days", id="days-null"),
            pytest.param({"reminder_repeat_days": "weekly"}, "repeat", id="repeat-string"),
        ],
    )
    def test_the_scheduled_run_completes_rather_than_raising(self, db, bad, suffix):
        """Two receipts, because the branches that read these values are
        mutually exclusive.

        `reminders_due` reads `days_after_due` only under `if not sent:` and
        `repeat_days` only in the `elif` that needs a previously sent reminder.
        With one receipt, whichever branch it does not take leaves its value
        unread, and the case for that value passes with the guard reverted while
        asserting nothing. One fresh receipt and one already reminded keeps both
        branches live, so every bad value here is genuinely consulted.
        """
        _org(db, {"payment_reminders_enabled": True, **bad})
        self._overdue_receipt(db, suffix=f"fresh-{suffix}")
        reminded = self._overdue_receipt(db, suffix=f"again-{suffix}")
        self._already_reminded(db, reminded)

        # Before this change: TypeError out of `reminders_due`, inside the
        # Celery task, with the receipt that triggered it nowhere in the message.
        result = run_scheduled_reminders(db)

        assert result["overdue_marked"] >= 1, (
            "the run reported no overdue receipt, so it never reached the "
            "comparison this test is about"
        )

    def test_the_run_still_honours_a_valid_max_count(self, db):
        """The control: the survival above must come from the fallback, not from
        the run skipping the work."""
        _org(db, {"payment_reminders_enabled": True, "reminder_max_count": 0})
        self._overdue_receipt(db, suffix="fresh-valid")
        reminded = self._overdue_receipt(db, suffix="again-valid")
        self._already_reminded(db, reminded)

        result = run_scheduled_reminders(db)

        assert result["overdue_marked"] >= 1
        assert result["reminders_sent"] == 0, (
            "max_count 0 means send none, and the run sent something anyway"
        )

class TestSaveOnlyIntegersAreRangeCheckedOnSave:
    """`membership_fee_due_days` and `membership_lapse_grace_days`.

    These two always had read-side protection: `int()` inside a `try`, clamped
    with `max(0, ...)`. What they lacked was anything refusing the value on the
    way in, so a 400-day grace period was stored and silently honoured.

    **Their reads are deliberately untouched.** `int()` accepts a numeric string,
    so `"5"` resolves to 5 today; routing them through `billing_int_rule` would
    reject that string and fall back to the default instead, reinterpreting a
    value an instance has already stored. Refusing it on the way in costs
    nothing, because no stored value is re-read.
    """

    @pytest.mark.parametrize("key", sorted(SAVE_ONLY_INT_RULES))
    @pytest.mark.parametrize(
        "value,case", [("5", "string"), (-1, "negative"), (366, "over-a-year")]
    )
    def test_settings_put_refuses_the_value(self, client, db, key, value, case):
        _org(db, {})
        client.cookies.update(_auth_cookie(_admin(db, f"so-{key}-{case}")))

        response = client.put("/api/v1/settings/", json={"features": {key: value}})

        assert response.status_code == 422, (
            f"settings accepted {key}={value!r} ({case})"
        )

    @pytest.mark.parametrize("key", sorted(SAVE_ONLY_INT_RULES))
    def test_zero_is_accepted(self, client, db, key):
        """0 means "due immediately" and "lapse immediately", both legitimate."""
        _org(db, {})
        client.cookies.update(_auth_cookie(_admin(db, f"so-zero-{key}")))

        response = client.put("/api/v1/settings/", json={"features": {key: 0}})

        assert response.status_code == 200
        assert response.json()["features"][key] == 0

    @pytest.mark.parametrize("key", sorted(SAVE_ONLY_INT_RULES))
    def test_a_stored_numeric_string_is_still_honoured_on_read(self, db, key):
        """The reason these reads were left alone, pinned so it stays true.

        If someone later routes these through `billing_int_rule`, this fails:
        the registry rejects a string and would hand back the default, changing
        what an instance already configured.
        """
        from app.domains.billing.lapse_service import lapse_grace_days
        from app.domains.billing.recurring_billing_service import membership_fee_due_days

        reader = {
            "membership_lapse_grace_days": lapse_grace_days,
            "membership_fee_due_days": membership_fee_due_days,
        }[key]
        _org(db, {key: "5"})

        assert reader(db) == 5


class TestBooleanFlagsAreTypeCheckedOnSave:
    """A non-boolean in a flag read as one.

    These reads cannot raise: truthiness is total. The wrong answer is the
    point. `bool("false")` is `True`, so a flag an admin meant to switch off
    reads as on, and the feature runs. Validating the type on the way in is what
    keeps an instance out of that state.

    Save-side only, on purpose. A read-side fallback would reinterpret a value
    already stored, and that is the one change in this area that would alter a
    running instance rather than preserve it.
    """

    @pytest.mark.parametrize("key", sorted(BOOL_KEYS | {"booking_waitlist_enabled"}))
    @pytest.mark.parametrize(
        "value,case",
        [("false", "the-string-false"), (0, "int-zero"), (None, "null")],
    )
    def test_settings_put_refuses_a_non_boolean(self, client, db, key, value, case):
        _org(db, {})
        client.cookies.update(_auth_cookie(_admin(db, f"bool-{key}-{case}")))

        response = client.put("/api/v1/settings/", json={"features": {key: value}})

        assert response.status_code == 422, (
            f"settings accepted {key}={value!r}; `bool({value!r})` is "
            f"{bool(value)}, so the flag would read as that whatever was meant"
        )

    @pytest.mark.parametrize("key", sorted(BOOL_KEYS | {"booking_waitlist_enabled"}))
    @pytest.mark.parametrize("value", [True, False])
    def test_settings_put_accepts_a_real_boolean(self, client, db, key, value):
        _org(db, {})
        client.cookies.update(_auth_cookie(_admin(db, f"bool-ok-{key}-{value}")))

        response = client.put("/api/v1/settings/", json={"features": {key: value}})

        assert response.status_code == 200
        assert response.json()["features"][key] is value
