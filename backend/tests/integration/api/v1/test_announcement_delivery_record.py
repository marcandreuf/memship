"""What the announcement fan-out records, as against what it could have sent.

``announcement_recipients.emailed`` was written once, at send time, from the
member's eligibility — an address, and no opt-out — and nothing ever revisited
it with what the fan-out managed. On an install with no mail transport, the
default state of a fresh one, an admin who broadcast to the whole club was told
every member had been emailed and none had (#228).

The two facts now have a column each: ``email_eligible`` is the audience
snapshot, ``email_sent`` the outcome. These tests drive the Celery task body
directly, because the failure only appears once the fan-out has run.
"""

from unittest.mock import patch

import pytest

from app.core.security.jwt import create_access_token
from app.core.security.password import hash_password
from app.domains.auth.models import User
from app.domains.communications.models import Announcement, AnnouncementRecipient
from app.domains.mailing.policy import CATALOG
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person
from app.tasks.communication_tasks import send_announcement_task


def _auth_cookie(user):
    return {"access_token": create_access_token(user.id)}


def _org(db):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(
            id=1,
            name="Test Organization",
            locale="es",
            timezone="Europe/Madrid",
            currency="EUR",
            date_format="DD/MM/YYYY",
            invoice_prefix="FAC",
            invoice_next_number=1,
            invoice_annual_reset=True,
        )
        db.add(org)
        db.flush()
    org.features = {"communications": True}
    # Announcements are `optional`, so the broadcast is off until switched on.
    org.communications_config = {
        "templates": {spec.key: {"enabled": True} for spec in CATALOG}
    }
    db.flush()
    return org


def _admin(db, suffix):
    person = Person(
        first_name="Club", last_name="Admin", email=f"{suffix}-a@example3f91ba.com"
    )
    db.add(person)
    db.flush()
    user = User(
        person_id=person.id,
        email=person.email,
        password_hash=hash_password("password123"),
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _member(db, suffix, opted_out=False):
    person = Person(
        first_name="Mem", last_name=suffix, email=f"{suffix}@example3f91ba.com"
    )
    db.add(person)
    db.flush()
    mt = MembershipType(name=f"T{suffix}", slug=f"t-{suffix}", base_price=0)
    db.add(mt)
    db.flush()
    member = Member(
        person_id=person.id,
        membership_type_id=mt.id,
        member_number=f"M-{suffix}",
        status="active",
        is_active=True,
        communication_preferences={
            "email": not opted_out,
            "sms": False,
            "push": False,
        },
    )
    db.add(member)
    db.flush()
    return member


def _sent_announcement(db, client, admin):
    ann = Announcement(
        subject="Hello",
        body="Body",
        target_type="all",
        status="draft",
        created_by_user_id=admin.id,
    )
    db.add(ann)
    db.flush()
    db.commit()
    response = client.post(
        f"/api/v1/announcements/{ann.id}/send", cookies=_auth_cookie(admin)
    )
    assert response.status_code == 200, response.text
    return ann.id


def _rows(db, ann_id):
    return {
        r.member_id: r
        for r in db.query(AnnouncementRecipient).filter(
            AnnouncementRecipient.announcement_id == ann_id
        )
    }


@pytest.fixture(autouse=True)
def _task_reads_the_test_session(db, monkeypatch):
    """The task opens its own session; point it at this test's transaction.

    It also closes that session when it is done, which detaches every ORM
    object the test is still holding. So everything crossing the ``run()`` call
    below is an id, re-queried afterwards — the same reason
    ``test_payment_reminders.py`` reads its row back with ``db.get``.
    """
    monkeypatch.setattr("app.db.session.SessionLocal", lambda: db)


class TestTheFanOutRecordsWhatItManaged:
    def test_a_delivered_mail_is_recorded_on_the_row(self, client, db):
        _org(db)
        admin = _admin(db, "ok")
        member_id = _member(db, "ok1").id
        ann_id = _sent_announcement(db, client, admin)

        with patch(
            "app.core.email.send_announcement_email", return_value=True
        ):
            send_announcement_task.run(ann_id)

        row = _rows(db, ann_id)[member_id]
        assert row.email_eligible is True
        assert row.email_sent is True

    def test_an_install_with_no_transport_reports_nothing_delivered(
        self, client, db
    ):
        """The case in the issue: a fresh install, before mail is configured.

        Every member is eligible and none is reachable, and the admin was told
        the opposite.
        """
        _org(db)
        admin = _admin(db, "notr")
        member_id = _member(db, "notr1").id
        ann_id = _sent_announcement(db, client, admin)

        with patch(
            "app.core.email.send_announcement_email", return_value=False
        ):
            send_announcement_task.run(ann_id)

        row = _rows(db, ann_id)[member_id]
        assert row.email_eligible is True
        assert row.email_sent is False

    def test_one_failure_does_not_taint_the_rest(self, client, db):
        """A bounce or a rejected address is per-recipient, and so is the row."""
        _org(db)
        admin = _admin(db, "mix")
        good_id = _member(db, "mixgood").id
        bad = _member(db, "mixbad")
        bad_id, bad_address = bad.id, bad.person.email
        ann_id = _sent_announcement(db, client, admin)

        def _selective(to, *args, **kwargs):
            return to != bad_address

        with patch("app.core.email.send_announcement_email", side_effect=_selective):
            send_announcement_task.run(ann_id)

        rows = _rows(db, ann_id)
        assert rows[good_id].email_sent is True
        assert rows[bad_id].email_sent is False

    def test_an_opted_out_member_is_never_attempted(self, client, db):
        """Not eligible, so the fan-out skips them and the row stays at False —
        which is "not delivered", and true."""
        _org(db)
        admin = _admin(db, "opt")
        opted_out_id = _member(db, "optout1", opted_out=True).id
        ann_id = _sent_announcement(db, client, admin)

        with patch(
            "app.core.email.send_announcement_email", return_value=True
        ) as send:
            send_announcement_task.run(ann_id)

        assert send.call_count == 0
        row = _rows(db, ann_id)[opted_out_id]
        assert row.email_eligible is False
        assert row.email_sent is False


class TestTheStatsSayWhichIsWhich:
    def test_eligible_and_delivered_are_reported_apart(self, client, db):
        _org(db)
        admin = _admin(db, "st")
        _member(db, "st1")
        _member(db, "st2")
        _member(db, "st3", opted_out=True)
        ann_id = _sent_announcement(db, client, admin)
        cookie = _auth_cookie(admin)

        with patch(
            "app.core.email.send_announcement_email", return_value=False
        ):
            send_announcement_task.run(ann_id)

        stats = client.get(
            f"/api/v1/announcements/{ann_id}/stats", cookies=cookie
        ).json()

        assert stats["recipient_count"] == 3
        assert stats["email_eligible_count"] == 2
        # Before #228 this read 2 — the audience, reported as deliveries.
        assert stats["emailed_count"] == 0

    def test_a_delivered_broadcast_counts_what_went_out(self, client, db):
        _org(db)
        admin = _admin(db, "st2")
        _member(db, "st2a")
        _member(db, "st2b")
        ann_id = _sent_announcement(db, client, admin)
        cookie = _auth_cookie(admin)

        with patch(
            "app.core.email.send_announcement_email", return_value=True
        ):
            send_announcement_task.run(ann_id)

        stats = client.get(
            f"/api/v1/announcements/{ann_id}/stats", cookies=cookie
        ).json()

        assert stats["email_eligible_count"] == 2
        assert stats["emailed_count"] == 2

    def test_an_announcement_with_no_outcome_recorded_reports_unknown(
        self, client, db
    ):
        """Rows written before #228 carry NULL. "We never recorded it" is not
        "nothing was delivered", and the API says so with null rather than 0."""
        _org(db)
        admin = _admin(db, "old")
        _member(db, "old1")
        ann_id = _sent_announcement(db, client, admin)

        db.query(AnnouncementRecipient).filter(
            AnnouncementRecipient.announcement_id == ann_id
        ).update({"email_sent": None})
        db.commit()

        stats = client.get(
            f"/api/v1/announcements/{ann_id}/stats", cookies=_auth_cookie(admin)
        ).json()

        assert stats["email_eligible_count"] == 1
        assert stats["emailed_count"] is None

    def test_the_recipient_list_carries_both(self, client, db):
        _org(db)
        admin = _admin(db, "rl")
        _member(db, "rl1")
        ann_id = _sent_announcement(db, client, admin)
        cookie = _auth_cookie(admin)

        with patch(
            "app.core.email.send_announcement_email", return_value=False
        ):
            send_announcement_task.run(ann_id)

        items = client.get(
            f"/api/v1/announcements/{ann_id}/recipients", cookies=cookie
        ).json()["items"]

        assert items[0]["email_eligible"] is True
        assert items[0]["emailed"] is False
