"""Organization settings schemas."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

Email = Annotated[str, StringConstraints(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)]


class OrganizationSettingsResponse(BaseModel):
    id: int
    name: str
    legal_name: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    logo_url: str | None = None
    tax_id: str | None = None
    locale: str
    timezone: str
    currency: str
    date_format: str
    brand_color: str | None = None
    bank_name: str | None = None
    bank_iban: str | None = None
    bank_bic: str | None = None
    invoice_prefix: str = "INV"
    invoice_next_number: int = 1
    invoice_annual_reset: bool | None = True
    member_number_prefix: str = ""
    member_number_padding: int = 4
    member_number_next: int = 1
    default_vat_rate: float | None = 21.00
    creditor_id: str | None = None
    sepa_format: str | None = None
    features: dict = {}
    custom_settings: dict = {}
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrganizationBrandingResponse(BaseModel):
    """What the portal shell renders before it knows who is looking: the club's
    identity, its contact block, and which features are switched on.

    Deliberately a hand-written subset rather than an exclusion list — a column
    added later is withheld by default, which is the direction a mistake should
    fall. Everything financial or administrative (``tax_id``, banking, invoice
    counters, member numbering, SEPA, ``custom_settings``, ``sso_config``) lives
    only on ``GET /settings`` behind ``settings.read``.
    """

    id: int
    name: str
    legal_name: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    logo_url: str | None = None
    locale: str
    timezone: str
    currency: str
    date_format: str
    brand_color: str | None = None
    # Which modules the club uses. The member-facing nav already reveals this;
    # `gender_options` lives here too and the profile form needs it.
    features: dict = {}
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrganizationSettingsUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    email: Email | None = None
    phone: str | None = Field(default=None, max_length=50)
    website: str | None = Field(default=None, max_length=500)
    logo_url: str | None = Field(default=None, max_length=500)
    tax_id: str | None = Field(default=None, max_length=50)
    locale: str | None = Field(default=None, pattern=r"^(es|ca|en)$")
    timezone: str | None = Field(default=None, max_length=50)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    date_format: str | None = Field(default=None, max_length=20)
    brand_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    bank_name: str | None = Field(default=None, max_length=255)
    bank_iban: str | None = Field(default=None, max_length=34, pattern=r"^[A-Z]{2}\d{2}[A-Z0-9]{4,30}$")
    bank_bic: str | None = Field(default=None, max_length=11, pattern=r"^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$")
    invoice_prefix: str | None = Field(default=None, max_length=10)
    invoice_next_number: int | None = Field(default=None, ge=1)
    invoice_annual_reset: bool | None = None
    member_number_prefix: str | None = Field(default=None, max_length=20)
    member_number_padding: int | None = Field(default=None, ge=1, le=10)
    default_vat_rate: float | None = Field(default=None, ge=0, le=100)
    creditor_id: str | None = Field(default=None, max_length=35)
    sepa_format: str | None = Field(default=None, pattern=r"^(pain\.008)$")
    features: dict | None = None
    custom_settings: dict | None = None
