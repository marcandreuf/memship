"""Billing domain schemas — concepts, receipts, mandates, remittances, providers."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# --- Concept schemas ---


class ConceptCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=50)
    description: str | None = None
    concept_type: str = Field(pattern=r"^(membership|activity|manual|service)$")
    default_amount: Decimal = Field(default=0, ge=0)
    vat_rate: Decimal = Field(default=21.00, ge=0, le=100)
    default_discount: Decimal | None = Field(default=None, ge=0)
    default_discount_type: str | None = Field(
        default=None, pattern=r"^(percentage|fixed)$"
    )
    accounting_code: str | None = Field(default=None, max_length=50)


class ConceptUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=50)
    description: str | None = None
    default_amount: Decimal | None = Field(default=None, ge=0)
    vat_rate: Decimal | None = Field(default=None, ge=0, le=100)
    default_discount: Decimal | None = Field(default=None, ge=0)
    default_discount_type: str | None = Field(
        default=None, pattern=r"^(percentage|fixed)$"
    )
    accounting_code: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None


class ConceptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str | None
    description: str | None
    concept_type: str
    default_amount: Decimal
    vat_rate: Decimal
    default_discount: Decimal | None
    default_discount_type: str | None
    accounting_code: str | None
    is_active: bool


# --- Receipt schemas ---


class ReceiptCreate(BaseModel):
    member_id: int
    concept_id: int | None = None
    registration_id: int | None = None
    origin: str = Field(pattern=r"^(membership|activity|manual|service)$")
    description: str = Field(min_length=1, max_length=500)
    base_amount: Decimal = Field(ge=0)
    vat_rate: Decimal = Field(default=21.00, ge=0, le=100)
    discount_amount: Decimal | None = Field(default=None, ge=0)
    discount_type: str | None = Field(
        default=None, pattern=r"^(percentage|fixed)$"
    )
    emission_date: date
    due_date: date | None = None
    billing_period_start: date | None = None
    billing_period_end: date | None = None
    notes: str | None = None
    is_batchable: bool = True


class ReceiptUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=1, max_length=500)
    base_amount: Decimal | None = Field(default=None, ge=0)
    vat_rate: Decimal | None = Field(default=None, ge=0, le=100)
    discount_amount: Decimal | None = Field(default=None, ge=0)
    discount_type: str | None = Field(
        default=None, pattern=r"^(percentage|fixed)$"
    )
    due_date: date | None = None
    notes: str | None = None
    is_batchable: bool | None = None


class ReceiptPayRequest(BaseModel):
    payment_method: str = Field(pattern=r"^(cash|bank_transfer|card|direct_debit)$")
    payment_date: date | None = None


class ReceiptReturnRequest(BaseModel):
    return_reason: str = Field(min_length=1, max_length=255)
    return_date: date | None = None


class ReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    receipt_number: str
    member_id: int
    concept_id: int | None
    registration_id: int | None
    remittance_id: int | None
    origin: str
    description: str
    base_amount: Decimal
    vat_rate: Decimal
    vat_amount: Decimal
    total_amount: Decimal
    discount_amount: Decimal | None
    discount_type: str | None
    status: str
    payment_method: str | None
    emission_date: date
    due_date: date | None
    payment_date: date | None
    return_date: date | None
    return_reason: str | None
    is_batchable: bool
    transaction_id: str | None
    billing_period_start: date | None
    billing_period_end: date | None
    notes: str | None
    created_by: int | None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ReceiptDetailResponse(ReceiptResponse):
    """Extended response with member and concept names for detail views."""

    member_name: str | None = None
    member_number: str | None = None
    concept_name: str | None = None


class GenerateMembershipFeesRequest(BaseModel):
    billing_period_start: date
    billing_period_end: date
    emission_date: date
    due_date: date | None = None


# --- SEPA Mandate schemas ---


class MandateCreate(BaseModel):
    member_id: int
    debtor_name: str = Field(min_length=1, max_length=255)
    debtor_iban: str = Field(
        min_length=5, max_length=34, pattern=r"^[A-Z]{2}\d{2}[A-Z0-9]{4,30}$"
    )
    debtor_bic: str | None = Field(
        default=None, max_length=11, pattern=r"^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$"
    )
    mandate_type: str = Field(default="recurrent", pattern=r"^(recurrent|one_off)$")
    signature_method: str = Field(default="paper", pattern=r"^(paper|digital)$")
    signed_at: date
    notes: str | None = None


class MandateUpdate(BaseModel):
    debtor_name: str | None = Field(default=None, min_length=1, max_length=255)
    debtor_iban: str | None = Field(
        default=None, min_length=5, max_length=34,
        pattern=r"^[A-Z]{2}\d{2}[A-Z0-9]{4,30}$",
    )
    debtor_bic: str | None = Field(
        default=None, max_length=11, pattern=r"^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$"
    )
    notes: str | None = None


class MandateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    member_id: int
    mandate_reference: str
    creditor_id: str
    debtor_name: str
    debtor_iban: str
    debtor_bic: str | None
    mandate_type: str
    signature_method: str
    status: str
    signed_at: date
    document_path: str | None
    cancelled_at: datetime | None
    notes: str | None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


# --- Remittance schemas ---


class RemittanceCreate(BaseModel):
    receipt_ids: list[int] = Field(min_length=1)
    due_date: date
    notes: str | None = None


class RemittanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    remittance_number: str
    remittance_type: str
    status: str
    emission_date: date
    due_date: date
    total_amount: Decimal
    receipt_count: int
    sepa_file_path: str | None
    creditor_name: str
    creditor_iban: str
    creditor_bic: str | None
    creditor_id: str
    notes: str | None
    created_by: int | None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RemittanceDetailResponse(RemittanceResponse):
    """Extended response with receipt list."""

    receipts: list[ReceiptResponse] = []


# --- Payment Provider schemas ---


class PaymentProviderCreate(BaseModel):
    provider_type: str = Field(min_length=1, max_length=50)
    display_name: str = Field(min_length=1, max_length=255)
    status: str = Field(default="disabled", pattern=r"^(active|test|disabled)$")
    config: dict = Field(default_factory=dict)
    is_default: bool = False


class PaymentProviderUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = Field(default=None, pattern=r"^(active|test|disabled)$")
    config: dict | None = None
    is_default: bool | None = None


class PaymentProviderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider_type: str
    display_name: str
    status: str
    config: dict
    is_default: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
