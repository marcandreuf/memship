"""A member's email opt-out, honoured by the funnel every member mail passes.

Before #230 the preference was read in exactly one place — the announcement
audience — so a member who had switched club email off still received booking
confirmations, activity registrations, receipts and payment reminders. The two
paths disagreed about what the same stored preference meant.

The gate now sits in ``_send_templated_outcome`` beside the organization's own
switch, and reaches the ``optional`` tier only: see
``policy.honours_member_opt_out`` for why ``operational`` and ``mandatory`` are
left alone.

The address is what the funnel has, so the member is resolved from it. These
tests pin the cases that resolution has to get right — a shared family address,
a cancelled member's stale row, an address with no member behind it at all.
"""

from unittest.mock import patch

import pytest

from app.core import email as email_module
from app.core.email import EmailOutcome
from app.domains.mailing.policy import CATALOG, honours_member_opt_out
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person

ADDRESS = "household@example7d31c9.com"

BOOKING_CONTEXT = {
    "member_name": "Alex",
    "space_name": "Court 1",
    "booking_date": "24/07/2026",
    "booking_time": "10:00",
    "cancellation_deadline_hours": 24,
}


def _org_with_everything_on(db):
    """Every template switched on, so only the member's choice is in play."""
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(id=1, name="Test Club")
        db.add(org)
        db.flush()
    org.communications_config = {
        "templates": {spec.key: {"enabled": True} for spec in CATALOG}
    }
    db.flush()
    return org


def _mtype(db, suffix):
    mt = MembershipType(name=f"T{suffix}", slug=f"t-{suffix}", base_price=0)
    db.add(mt)
    db.flush()
    return mt


def _member(db, suffix, email=ADDRESS, opted_out=False, is_active=True):
    person = Person(first_name="Mem", last_name=suffix, email=email)
    db.add(person)
    db.flush()
    member = Member(
        person_id=person.id,
        membership_type_id=_mtype(db, suffix).id,
        member_number=f"M-{suffix}",
        status="active",
        is_active=is_active,
        communication_preferences={
            "email": not opted_out,
            "sms": False,
            "push": False,
        },
    )
    db.add(member)
    db.flush()
    return member


@pytest.fixture(autouse=True)
def _funnel_reads_the_test_session(db, monkeypatch):
    """Point the funnel's own session at this test's transaction.

    Both gates open a short-lived ``SessionLocal`` of their own rather than
    taking a session from the caller, which is what lets a Celery task or the
    reminder service send without carrying one. The ``db`` fixture never
    commits, so a genuinely new session would see none of the rows a test just
    wrote, and every template would read as switched off. Same approach as
    ``test_payment_reminders.py``.
    """
    monkeypatch.setattr("app.db.session.SessionLocal", lambda: db)


@pytest.fixture
def transport():
    """Hold the transport open and count what reaches it."""
    with patch("app.core.email.send_email", return_value=True) as mock:
        yield mock


def _booking_confirmation(to=ADDRESS):
    """An ``optional`` template, and the one the issue reports on."""
    return email_module.send_booking_confirmation_email(
        to, "Alex", "Court 1", "24/07/2026", "10:00", 24
    )


def _booking_outcome(to=ADDRESS):
    return email_module._send_templated_outcome(
        "booking_confirmation",
        to,
        "es",
        dict(BOOKING_CONTEXT),
        subject_args={"space": "Court 1"},
    )


class TestTheOptOutIsHonouredByTheFunnel:
    def test_an_optional_mail_is_suppressed(self, db, transport):
        _org_with_everything_on(db)
        _member(db, "optout", opted_out=True)
        db.commit()

        assert _booking_confirmation() is False
        transport.assert_not_called()

    def test_a_member_who_did_not_opt_out_still_receives_it(self, db, transport):
        _org_with_everything_on(db)
        _member(db, "optin", opted_out=False)
        db.commit()

        assert _booking_confirmation() is True
        transport.assert_called_once()

    def test_the_outcome_says_opted_out_not_suppressed(self, db, transport):
        """An admin reading a delivery record must not see their own setting
        blamed for a member's choice — the distinction #219 established."""
        _org_with_everything_on(db)
        _member(db, "outcome", opted_out=True)
        db.commit()

        assert _booking_outcome() is EmailOutcome.OPTED_OUT


class TestWhichTiersTheOptOutReaches:
    def test_it_does_not_reach_an_operational_mail(self, db, transport):
        """``receipt_delivery`` and ``payment_reminder`` live in this tier — a
        member must not be able to stop their own invoices arriving."""
        _org_with_everything_on(db)
        _member(db, "operational", opted_out=True)
        db.commit()

        sent = email_module.send_booking_promoted_email(
            ADDRESS, "Alex", "Court 1", "24/07/2026", "10:00"
        )
        assert sent is True
        transport.assert_called_once()

    def test_it_does_not_reach_a_mandatory_mail(self, db, transport):
        """Account access rests on contract, not consent."""
        _org_with_everything_on(db)
        _member(db, "mandatory", opted_out=True)
        db.commit()

        sent = email_module.send_password_reset_email(
            ADDRESS, "Alex", "https://club.test/reset?t=x"
        )
        assert sent is True
        transport.assert_called_once()

    def test_the_tier_predicate_is_exactly_the_optional_templates(self):
        reached = {spec.key for spec in CATALOG if honours_member_opt_out(spec.key)}
        assert reached == {spec.key for spec in CATALOG if spec.tier == "optional"}

    def test_an_uncatalogued_key_is_never_silenced(self):
        """It has no tier, the same reason ``always_sends`` lets it through."""
        assert honours_member_opt_out("mailing_test") is False


class TestResolvingTheMemberFromTheAddress:
    def test_a_shared_address_sends_while_anyone_still_wants_mail(
        self, db, transport
    ):
        """``persons.email`` is non-unique on purpose: a guardian receives a
        minor's mail. The guardian's own opt-out must not silence the child."""
        _org_with_everything_on(db)
        _member(db, "guardian", opted_out=True)
        _member(db, "child", opted_out=False)
        db.commit()

        assert _booking_confirmation() is True
        transport.assert_called_once()

    def test_a_shared_address_is_silenced_once_everyone_has_opted_out(
        self, db, transport
    ):
        _org_with_everything_on(db)
        _member(db, "adult-a", opted_out=True)
        _member(db, "adult-b", opted_out=True)
        db.commit()

        assert _booking_confirmation() is False
        transport.assert_not_called()

    def test_a_cancelled_member_does_not_decide_for_the_household(
        self, db, transport
    ):
        _org_with_everything_on(db)
        _member(db, "ex", opted_out=True, is_active=False)
        _member(db, "current", opted_out=False)
        db.commit()

        assert _booking_confirmation() is True
        transport.assert_called_once()

    def test_an_address_with_no_member_behind_it_is_not_opted_out(
        self, db, transport
    ):
        """Staff, an applicant, anyone not yet a member: no preference to read."""
        _org_with_everything_on(db)
        db.commit()

        assert _booking_confirmation("nobody@example7d31c9.com") is True
        transport.assert_called_once()

    def test_a_member_with_no_preference_stored_receives_mail(self, db, transport):
        """Rows predating the column's default carry NULL, which is not a
        choice the member made."""
        _org_with_everything_on(db)
        member = _member(db, "nullprefs")
        member.communication_preferences = None
        db.commit()

        assert _booking_confirmation() is True
        transport.assert_called_once()

    def test_the_address_matches_regardless_of_case(self, db, transport):
        _org_with_everything_on(db)
        _member(db, "case", email="Household@Example7d31c9.com", opted_out=True)
        db.commit()

        assert _booking_confirmation("household@example7d31c9.com") is False
        transport.assert_not_called()


class TestTheOrganizationsSwitchStillComesFirst:
    def test_a_disabled_template_reports_suppressed_not_opted_out(
        self, db, transport
    ):
        """The two gates answer to different people and must stay legible."""
        org = _org_with_everything_on(db)
        org.communications_config = {
            "templates": {"booking_confirmation": {"enabled": False}}
        }
        _member(db, "both", opted_out=True)
        db.commit()

        assert _booking_outcome() is EmailOutcome.SUPPRESSED
        transport.assert_not_called()
