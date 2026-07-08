"""Reports schemas — annual summary aggregates."""

from pydantic import BaseModel


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
