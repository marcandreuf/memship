"""``org_today`` is the club's date, not the container's (#271)."""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import app.core.clock as clock
from app.core.clock import org_timezone, org_today
from app.domains.organizations.models import OrganizationSettings


def _org(db, tz):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(id=1, name="Clock Club")
        db.add(org)
    org.timezone = tz
    db.flush()


class _FrozenDatetime(datetime):
    """``datetime.now(tz)`` pinned to 23:30 UTC on 31 December."""

    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 12, 31, 23, 30, tzinfo=timezone.utc).astimezone(tz)


def test_the_club_is_already_in_the_new_year(db, monkeypatch):
    _org(db, "Europe/Madrid")
    monkeypatch.setattr(clock, "datetime", _FrozenDatetime)

    assert org_today(db) == date(2027, 1, 1)


def test_a_western_club_is_still_in_the_old_year(db, monkeypatch):
    _org(db, "Atlantic/Canary")
    monkeypatch.setattr(clock, "datetime", _FrozenDatetime)

    assert org_today(db) == date(2026, 12, 31)


def test_an_unknown_timezone_falls_back_to_madrid(db):
    _org(db, "Mars/Olympus_Mons")
    assert org_timezone(db) == ZoneInfo("Europe/Madrid")


def test_no_settings_row_falls_back_to_madrid(db):
    db.query(OrganizationSettings).delete()
    db.flush()
    assert org_timezone(db) == ZoneInfo("Europe/Madrid")
