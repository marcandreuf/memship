"""Reports service — annual summary aggregates.

Feeds both the Annual Summary page (any year) and the admin dashboard's central
finance graph (current year: revenue + outstanding by month). Keeping the
aggregation here means both surfaces read the same numbers.
"""

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.domains.activities.models import Activity, Registration
from app.domains.billing.models import Receipt
from app.domains.members.models import Member
from app.domains.reports.schemas import ActivityParticipation, AnnualSummary

OUTSTANDING_STATUSES = ("pending", "emitted", "overdue")


def _buckets_float(rows) -> list[float]:
    buckets = [0.0] * 12
    for month, value in rows:
        if month is not None:
            buckets[int(month) - 1] = round(float(value or 0), 2)
    return buckets


def _buckets_int(rows) -> list[int]:
    buckets = [0] * 12
    for month, value in rows:
        if month is not None:
            buckets[int(month) - 1] = int(value or 0)
    return buckets


def annual_summary(db: Session, year: int) -> AnnualSummary:
    """Build the financial + membership summary for a single calendar year."""
    # Revenue collected per month — paid receipts, bucketed by payment date.
    revenue_rows = (
        db.query(
            extract("month", Receipt.payment_date),
            func.coalesce(func.sum(Receipt.total_amount), 0),
        )
        .filter(
            Receipt.is_active.is_(True),
            Receipt.status == "paid",
            extract("year", Receipt.payment_date) == year,
        )
        .group_by(extract("month", Receipt.payment_date))
        .all()
    )

    # Outstanding per month — unpaid receipts, bucketed by emission date.
    outstanding_rows = (
        db.query(
            extract("month", Receipt.emission_date),
            func.coalesce(func.sum(Receipt.total_amount), 0),
        )
        .filter(
            Receipt.is_active.is_(True),
            Receipt.status.in_(OUTSTANDING_STATUSES),
            extract("year", Receipt.emission_date) == year,
        )
        .group_by(extract("month", Receipt.emission_date))
        .all()
    )

    # New members per month — bucketed by join date.
    new_member_rows = (
        db.query(extract("month", Member.joined_at), func.count(Member.id))
        .filter(extract("year", Member.joined_at) == year)
        .group_by(extract("month", Member.joined_at))
        .all()
    )
    new_members_by_month = _buckets_int(new_member_rows)
    new_members = sum(new_members_by_month)

    # Members lost this year — cancelled/expired, by status-change date.
    lost_members = (
        db.query(func.count(Member.id))
        .filter(
            Member.status.in_(("cancelled", "expired")),
            extract("year", Member.status_changed_at) == year,
        )
        .scalar()
    ) or 0

    active_members = (
        db.query(func.count(Member.id)).filter(Member.status == "active").scalar()
    ) or 0
    total_members = db.query(func.count(Member.id)).scalar() or 0

    # Top activities by confirmed registrations — activities starting in the year.
    participation_rows = (
        db.query(Activity.name, func.count(Registration.id))
        .join(Registration, Registration.activity_id == Activity.id)
        .filter(
            Registration.status == "confirmed",
            extract("year", Activity.starts_at) == year,
        )
        .group_by(Activity.id, Activity.name)
        .order_by(func.count(Registration.id).desc(), Activity.name)
        .limit(10)
        .all()
    )

    return AnnualSummary(
        year=year,
        revenue_by_month=_buckets_float(revenue_rows),
        outstanding_by_month=_buckets_float(outstanding_rows),
        new_members_by_month=new_members_by_month,
        active_members=active_members,
        total_members=total_members,
        new_members=new_members,
        lost_members=lost_members,
        net_growth=new_members - lost_members,
        activity_participation=[
            ActivityParticipation(activity_name=name, count=count)
            for name, count in participation_rows
        ],
    )
