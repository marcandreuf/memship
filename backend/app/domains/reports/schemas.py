"""Reports schemas — annual summary aggregates and the paid-tier clean-up list."""

from datetime import date

from pydantic import BaseModel

from app.core.pagination import PageMeta


class ActivityParticipation(BaseModel):
    activity_name: str
    count: int


class AnnualSummary(BaseModel):
    year: int
    # 12 entries each, index 0 = January
    revenue_by_month: list[float]
    outstanding_by_month: list[float]
    new_members_by_month: list[int]
    active_members: int
    total_members: int
    new_members: int
    lost_members: int
    net_growth: int
    activity_participation: list[ActivityParticipation]


class PaidTierMember(BaseModel):
    member_id: int
    member_number: str | None
    full_name: str
    email: str | None
    status: str
    joined_at: date
    membership_type_id: int
    membership_type_name: str
    base_price: float
    billing_frequency: str
    unpaid_receipts: int
    unpaid_amount: float


class PaidTierWithoutPurchase(BaseModel):
    meta: PageMeta
    items: list[PaidTierMember]
