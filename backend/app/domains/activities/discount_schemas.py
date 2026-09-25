"""Discount code schemas."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.schema_types import NonBlank, refuse_null
from app.domains.shared.enums import DiscountType


def normalize_code(value: str | None) -> str | None:
    """Codes are printed on posters and retyped from messages in whatever case
    the member likes; ``summer20`` and ``SUMMER20`` are the same code. Stored
    and looked up in upper case, so the unique constraint and the lookup agree."""
    if value is None:
        return None
    return value.strip().upper()


class DiscountCodeCreate(BaseModel):
    code: NonBlank(50)

    _normalize_code = field_validator("code")(normalize_code)
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
    code: NonBlank(50) | None = None

    _normalize_code = field_validator("code")(normalize_code)
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

    _not_null = field_validator("code")(refuse_null)


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
    code: NonBlank(50)

    _normalize_code = field_validator("code")(normalize_code)


class ValidateDiscountResponse(BaseModel):
    """What a code is worth, before and after tax.

    The ``*_total`` figures are what the member will be charged; the plain
    amounts are the bases VAT is added to when the receipt is raised. Quoting a
    discounted base alone understates the saving's effect on the invoice (#220).
    """

    valid: bool
    discount_type: str | None = None
    discount_value: float | None = None
    original_amount: float | None = None
    discounted_amount: float | None = None
    original_total: float | None = None
    discounted_total: float | None = None
    error: str | None = None
