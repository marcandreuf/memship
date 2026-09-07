"""Reports service — annual summary aggregates and the paid-tier clean-up list.

The annual summary feeds both the Annual Summary page (any year) and the admin
dashboard's central finance graph (current year: revenue + outstanding by
month). Keeping the aggregation here means both surfaces read the same numbers.
"""

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.core.pagination import paginate
from app.domains.activities.models import Activity, Registration
from app.domains.billing.models import Receipt
from app.domains.members.models import Member, MembershipType
from app.domains.persons.models import Person
from app.domains.reports.schemas import (
    ActivityParticipation,
    AnnualSummary,
    PaidTierMember,
    PaidTierWithoutPurchase,
)

OUTSTANDING_STATUSES = ("pending", "emitted", "overdue")

# Everything a membership receipt can be while the money has not arrived. A
# cancelled one is a charge the club withdrew, so it counts as no charge at all.
UNPAID_STATUSES = ("new", "pending", "emitted", "overdue")

# Statuses the club has already closed: nobody bills them and nobody is waiting
# on a decision about them, so they are not clean-up work.
SETTLED_MEMBER_STATUSES = ("cancelled", "expired")


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


def paid_tier_without_purchase(
    db: Session, page: int = 1, per_page: int = 20
) -> PaidTierWithoutPurchase:
    """Members sitting on a priced tier that nobody has ever paid for.

    Until sign-ups landed on a free default tier, self-registration put the new
    member on whichever membership type happened to have the lowest id — a
    50 EUR plan on a seeded install. This lists who that left behind.

    "No purchase behind them" is read as *no membership receipt has ever reached
    ``paid``*. There is no record of buying a membership yet, and a settled
    receipt is the closest thing the schema has: money changed hands against a
    membership fee, which takes a human on both sides. Anything weaker would
    clear the very people the bug hurt — a member the recurring run has already
    billed has membership receipts, they are simply unpaid, and those are the
    damage rather than the evidence. So the unpaid ones are counted and totalled
    per row instead of excluding anybody: that total is what the club is
    currently asking for and may want to withdraw.

    Members the club has already closed (cancelled, expired, deactivated) are
    left out — nothing bills them and no decision is pending. The dearest tier
    comes first, since that is where the accruing fee is largest.
    """
    has_paid_membership_receipt = (
        db.query(Receipt.id)
        .filter(
            Receipt.member_id == Member.id,
            Receipt.origin == "membership",
            Receipt.status == "paid",
            Receipt.is_active.is_(True),
        )
        .exists()
    )

    unpaid = (
        db.query(
            Receipt.member_id.label("member_id"),
            func.count(Receipt.id).label("receipts"),
            func.coalesce(func.sum(Receipt.total_amount), 0).label("amount"),
        )
        .filter(
            Receipt.origin == "membership",
            Receipt.status.in_(UNPAID_STATUSES),
            Receipt.is_active.is_(True),
        )
        .group_by(Receipt.member_id)
        .subquery()
    )

    query = (
        db.query(Member, Person, MembershipType, unpaid.c.receipts, unpaid.c.amount)
        .join(Person, Member.person_id == Person.id)
        .join(MembershipType, Member.membership_type_id == MembershipType.id)
        .outerjoin(unpaid, unpaid.c.member_id == Member.id)
        .filter(
            MembershipType.base_price > 0,
            Member.is_active.is_(True),
            Member.status.notin_(SETTLED_MEMBER_STATUSES),
            ~has_paid_membership_receipt,
        )
        .order_by(MembershipType.base_price.desc(), Member.id)
    )

    rows, meta = paginate(query, page, per_page)

    return PaidTierWithoutPurchase(
        meta=meta,
        items=[
            PaidTierMember(
                member_id=member.id,
                member_number=member.member_number,
                full_name=f"{person.first_name} {person.last_name}",
                email=person.email,
                status=member.status,
                joined_at=member.joined_at,
                membership_type_id=mtype.id,
                membership_type_name=mtype.name,
                base_price=float(mtype.base_price or 0),
                billing_frequency=mtype.billing_frequency,
                unpaid_receipts=int(receipts or 0),
                unpaid_amount=round(float(amount or 0), 2),
            )
            for member, person, mtype, receipts, amount in rows
        ],
    )
