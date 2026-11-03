"""What ``organization_settings.features`` accepts on save, and what it falls back to.

Three defects in one place, because they share one validator and one endpoint:
the configuration values guarded at both ends (#493), the canonical key set that
lets a misspelled flag be refused (#494), and the notification address validated
like every other address in the product (#495).

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

The key check (#494) is save-side only for the opposite reason: the sparse merge
in ``api/v1/endpoints/settings.py`` runs *after* the schema, so a stored stray
key is never re-validated and an instance holding one stays able to save. That
order is load-bearing and
``test_a_stored_stray_key_does_not_block_an_unrelated_save`` is what pins it.
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
from app.domains.billing.rules import FEATURE_KEYS as BILLING_FEATURE_KEYS
from app.domains.bookings.rules import FEATURE_KEYS as BOOKING_FEATURE_KEYS
from app.cli.demo_data import DEMO_FEATURES
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.feature_keys import (
    ACTION_GATE_KEYS,
    FEATURE_KEYS,
    MODULE_GATE_KEYS,
    OFFERED_VALUE_KEYS,
    POLICY_KEYS,
)
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


# Every canonical key paired with a value the code honours. This one literal
# does two jobs: it pins the canonical set, so adding a flag to the product is a
# deliberate edit with a visible diff here, and it drives the acceptance mirror
# below, so a key cannot be added to the set without something proving the
# endpoint actually takes it.
CANONICAL = {
    # Module gates — 404 when off.
    "bookings": True,
    "communications": True,
    "custom_profile_fields": True,
    "custom_roles": True,
    "member_card": True,
    # Action gate — 403 when off.
    "public_registration": True,
    # Policy.
    "registration_requires_approval": True,
    # Offered values.
    "gender_options": [
        {"value": "male", "label_es": "Hombre", "label_ca": "Home", "label_en": "Male"}
    ],
    # Bookings configuration.
    "booking_window_days": 14,
    "booking_cancellation_deadline_hours": 24,
    "booking_waitlist_enabled": True,
    # Billing configuration.
    "membership_fee_due_days": 7,
    "membership_lapse_grace_days": 21,
    "membership_lapse_enabled": True,
    "payment_reminders_enabled": True,
    "recurring_billing_enabled": True,
    "reminder_days_after_due": 3,
    "reminder_repeat_days": 7,
    "reminder_max_count": 3,
    "recurring_billing_day": 1,
    "billing_notification_email": "tesoreria@club.example",
}


class TestTheCanonicalSetIsPinned:
    """The list exists so a typo can be refused; these keep the list honest.

    Before #494 there was no canonical list anywhere in the code, and the
    nearest thing was a demo seed naming nineteen of the twenty-one flags.
    """

    def test_the_set_is_exactly_what_this_test_pins(self):
        assert FEATURE_KEYS == frozenset(CANONICAL), (
            "the canonical feature set changed. Adding a flag to the product is "
            "meant to be a deliberate edit in both places: register it in its "
            "domain's rules.py (or in feature_keys.py if it is a gate), and give "
            "it a valid value in CANONICAL here so the acceptance mirror covers it"
        )

    def test_the_groups_do_not_overlap(self):
        """A key classified twice means the specification's four classes have
        stopped being classes. Caught exactly this while writing #494, with
        `public_registration` declared both a module gate and an action gate."""
        groups = {
            "module gates": MODULE_GATE_KEYS,
            "action gates": ACTION_GATE_KEYS,
            "offered values": OFFERED_VALUE_KEYS,
            "policy": POLICY_KEYS,
            "billing": BILLING_FEATURE_KEYS,
            "bookings": BOOKING_FEATURE_KEYS,
        }
        for left, left_keys in groups.items():
            for right, right_keys in groups.items():
                if left >= right:
                    continue
                assert not left_keys & right_keys, (
                    f"{sorted(left_keys & right_keys)} is declared both in "
                    f"{left} and in {right}"
                )

    def test_every_key_the_demo_seed_writes_is_recognised(self):
        """`seed demo` writes nineteen of them. A flag added to the demo without
        being registered would otherwise 422 the first time an admin saved it."""
        assert set(DEMO_FEATURES) <= FEATURE_KEYS, (
            f"the demo seed writes {sorted(set(DEMO_FEATURES) - FEATURE_KEYS)}, "
            f"which the settings endpoint would refuse"
        )


class TestUnrecognisedKeysAreRefusedOnSave:
    @pytest.mark.parametrize(
        "key",
        [
            pytest.param("booking_window_day", id="singular-typo"),
            pytest.param("reminder_max_cont", id="dropped-letter"),
            pytest.param("payment_reminders", id="truncated"),
            pytest.param("memberCardEnabled", id="wrong-convention"),
        ],
    )
    def test_settings_put_refuses_a_misspelled_flag(self, client, db, key):
        _org(db, {})
        client.cookies.update(_auth_cookie(_admin(db, f"unk-{key}")))

        response = client.put("/api/v1/settings/", json={"features": {key: True}})

        assert response.status_code == 422, (
            f"settings accepted the unknown key {key!r} with "
            f"{response.status_code}; the sparse merge would store it forever "
            f"and nothing would ever say the setting does nothing"
        )

    def test_the_refusal_names_the_offending_key(self, client, db):
        """The defect was a silent no-op, so a 422 that does not say which key
        is wrong only moves the guesswork rather than ending it."""
        _org(db, {})
        client.cookies.update(_auth_cookie(_admin(db, "unk-named")))

        response = client.put(
            "/api/v1/settings/", json={"features": {"booking_window_day": 7}}
        )

        assert response.status_code == 422
        assert "booking_window_day" in response.text

    @pytest.mark.parametrize("key,value", sorted(CANONICAL.items()))
    def test_settings_put_accepts_every_canonical_key(self, client, db, key, value):
        """The mirror. Without it the refusals above could pass by refusing
        every key, which would break every settings form in the product."""
        _org(db, {})
        client.cookies.update(_auth_cookie(_admin(db, f"can-{key}")))

        response = client.put("/api/v1/settings/", json={"features": {key: value}})

        assert response.status_code == 200, (
            f"settings refused the canonical key {key!r}: {response.text}"
        )
        assert response.json()["features"][key] == value

    @pytest.mark.parametrize(
        "features",
        [
            pytest.param({}, id="nothing-at-all"),
            pytest.param({"custom_roles": True}, id="a-single-key"),
        ],
    )
    def test_absence_stays_legitimate(self, client, db, features):
        """The rule is "an unknown key is refused", never "all known keys are
        required". A fresh `seed --test` stores fifteen of the twenty-one and the
        rest resolve through their read-side defaults."""
        _org(db, {})
        client.cookies.update(_auth_cookie(_admin(db, f"abs-{len(features)}")))

        response = client.put("/api/v1/settings/", json={"features": features})

        assert response.status_code == 200, response.text

    def test_a_stored_stray_key_does_not_block_an_unrelated_save(self, client, db):
        """Keys already stored are left alone rather than dropped by a migration,
        so an instance holding one has to stay able to save.

        This works because the merge in `api/v1/endpoints/settings.py` runs
        *after* the schema: only the keys a request carries reach the validator,
        and the stored row is never re-validated. If that order ever inverts,
        every instance with a stray key would be locked out of its own settings.
        """
        _org(db, {"legacy_flag_nobody_remembers": True})
        client.cookies.update(_auth_cookie(_admin(db, "stray")))

        response = client.put(
            "/api/v1/settings/", json={"features": {"custom_roles": False}}
        )

        assert response.status_code == 200, response.text
        features = response.json()["features"]
        assert features["custom_roles"] is False
        assert features["legacy_flag_nobody_remembers"] is True, (
            "the stray was dropped; #494 decided to leave stored keys alone"
        )

    def test_replaying_the_whole_stored_snapshot_is_refused(self, client, db):
        """The other half of the decision, and the one with a client consequence.

        A stored stray is tolerated only because it is never re-sent. A client
        that reads `features` and posts the whole dict back *does* re-send it,
        so it is refused like any other unknown key, and on an instance holding
        a stray that client can no longer save at all.

        This is deliberate rather than an oversight: the endpoint merges sparsely
        precisely so that no form needs to replay a snapshot, and replaying one is
        itself the lost update that merging removed (#314). `roles-settings.tsx`
        was doing exactly this and was fixed alongside #494; this test is what
        stops the pattern coming back silently.
        """
        _org(db, {"legacy_flag_nobody_remembers": True, "custom_roles": True})
        client.cookies.update(_auth_cookie(_admin(db, "stray-replay")))

        stored = client.get("/api/v1/settings/").json()["features"]
        response = client.put("/api/v1/settings/", json={"features": stored})

        assert response.status_code == 422, (
            "replaying the stored snapshot was accepted; a client doing this "
            "would silently keep re-writing keys nothing recognises"
        )
        assert "legacy_flag_nobody_remembers" in response.text


class TestTheNotificationAddressIsValidatedOnSave:
    """`billing_notification_email` was the one address stored without
    validation (#495), because it lives in `features` and so bypassed the shared
    schema types entirely.

    Its consequence is quiet by design: the send is best-effort so a failure
    cannot fail the billing run, which means a malformed address raises nothing
    a user sees and the summary just never arrives.
    """

    @pytest.mark.parametrize(
        "value",
        [
            pytest.param("tesoreria", id="no-at-sign"),
            pytest.param("tesoreria@club", id="no-tld"),
            pytest.param("tesoreria club@example.test", id="internal-space"),
            pytest.param("josé@club.example", id="non-ascii-local-part"),
            pytest.param(123, id="not-a-string"),
            pytest.param(True, id="a-boolean"),
        ],
    )
    def test_settings_put_refuses_a_malformed_address(self, client, db, value):
        _org(db, {})
        client.cookies.update(_auth_cookie(_admin(db, f"mail-bad-{value}")))

        response = client.put(
            "/api/v1/settings/",
            json={"features": {"billing_notification_email": value}},
        )

        assert response.status_code == 422, (
            f"settings accepted {value!r} as the notification address; the "
            f"billing summary would silently never arrive"
        )

    def test_the_address_is_normalised_the_way_every_other_address_is(
        self, client, db
    ):
        """Stored as it will be handed to the mail transport, not as typed."""
        _org(db, {})
        client.cookies.update(_auth_cookie(_admin(db, "mail-norm")))

        response = client.put(
            "/api/v1/settings/",
            json={"features": {"billing_notification_email": "  Tesoreria@Club.Example  "}},
        )

        assert response.status_code == 200, response.text
        assert (
            response.json()["features"]["billing_notification_email"]
            == "tesoreria@club.example"
        )

    def test_a_development_domain_validates(self, client, db):
        """`Email` is a regex rather than `EmailStr` on purpose, so `.test` and
        `.local` work in development."""
        _org(db, {})
        client.cookies.update(_auth_cookie(_admin(db, "mail-dev")))

        response = client.put(
            "/api/v1/settings/",
            json={"features": {"billing_notification_email": "tesoreria@club.test"}},
        )

        assert response.status_code == 200, response.text

    @pytest.mark.parametrize(
        "value", [pytest.param("", id="empty-string"), pytest.param(None, id="null")]
    )
    def test_clearing_the_address_is_allowed(self, client, db, value):
        """Both reads are guarded by truthiness and both of these already mean
        "send no notification", so an admin switching the notification off must
        not be refused."""
        _org(db, {"billing_notification_email": "old@club.example"})
        client.cookies.update(_auth_cookie(_admin(db, f"mail-clear-{value!r}")))

        response = client.put(
            "/api/v1/settings/",
            json={"features": {"billing_notification_email": value}},
        )

        assert response.status_code == 200, response.text
        assert not response.json()["features"]["billing_notification_email"]
