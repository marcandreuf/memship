"""Today, as the club sees it.

The API and the beat run in containers on UTC; the club's day is
``organization_settings.timezone``. Between the two midnights — 22:00 to
24:00 UTC in summer for Madrid — ``date.today()`` is yesterday to everyone
looking at the screen, and a receipt stamped then carries the wrong date. A
credit note issued at 00:30 on 1 January took the old year's last number and
was filed in the old year's series (#271).

Every date the application stamps on a document or compares a due date
against comes from here. The bookings service had the same helper privately;
this is that one, lifted.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.domains.organizations.models import OrganizationSettings

DEFAULT_TIMEZONE = "Europe/Madrid"


def org_timezone(db: Session) -> ZoneInfo:
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    name = getattr(org, "timezone", None)
    if not isinstance(name, str) or not name:
        name = None
    try:
        return ZoneInfo(name or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TIMEZONE)


def org_now(db: Session) -> datetime:
    """The current instant, aware, in the club's timezone."""
    return datetime.now(org_timezone(db))


def org_today(db: Session) -> date:
    """The club's calendar date right now."""
    return org_now(db).date()
