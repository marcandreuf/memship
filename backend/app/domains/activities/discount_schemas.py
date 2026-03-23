"""Discount code schemas."""

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.domains.shared.enums import DiscountType


class DiscountCodeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=2000)
    discount_type: DiscountType
    discount_value: float = Field(gt=0)
    max_uses: int | None = Field(default=None, ge=1)
    valid_from: datetime | None = None
    valid_until: datetime | None = None

    @model_validator(mode="after")
    def validate_discount(self):
        if self.discount_type == DiscountType.PERCENTAGE and self.discount_value > 100:
            raise ValueError("Percentage discount cannot exceed 100")
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be after valid_from")
        return self


class DiscountCodeUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=2000)
    discount_type: DiscountType | None = None
    discount_value: float | None = Field(default=None, gt=0)
    max_uses: int | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_discount(self):
        if self.discount_type == DiscountType.PERCENTAGE and self.discount_value is not None and self.discount_value > 100:
            raise ValueError("Percentage discount cannot exceed 100")
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be after valid_from")
        return self


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
