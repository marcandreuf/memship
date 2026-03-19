"""Discount code schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class DiscountCodeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    description: str | None = None
    discount_type: str = Field(pattern="^(percentage|fixed)$")
    discount_value: float = Field(gt=0)
    max_uses: int | None = Field(default=None, ge=1)
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class DiscountCodeUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = None
    discount_type: str | None = Field(default=None, pattern="^(percentage|fixed)$")
    discount_value: float | None = Field(default=None, gt=0)
    max_uses: int | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    is_active: bool | None = None


class DiscountCodeResponse(BaseModel):
    id: int
    activity_id: int
    code: str
    description: str | None = None
    discount_type: str
    discount_value: float
    max_uses: int | None = None
    current_uses: int = 0
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ValidateDiscountRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50)


class ValidateDiscountResponse(BaseModel):
    valid: bool
    discount_type: str | None = None
    discount_value: float | None = None
    original_amount: float | None = None
    discounted_amount: float | None = None
    error: str | None = None
