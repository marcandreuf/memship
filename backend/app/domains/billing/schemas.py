"""Billing domain schemas — concepts, receipts, mandates, remittances, providers."""

import re
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

from app.core.schema_types import NonBlank, refuse_null


# --- Concept schemas ---


class ConceptCreate(BaseModel):
    name: NonBlank(255)
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
    name: NonBlank(255) | None = None
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

    _not_null = field_validator("name")(refuse_null)


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
    description: NonBlank(500)
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
    description: NonBlank(500) | None = None
    base_amount: Decimal | None = Field(default=None, ge=0)
    vat_rate: Decimal | None = Field(default=None, ge=0, le=100)
    discount_amount: Decimal | None = Field(default=None, ge=0)
    discount_type: str | None = Field(
        default=None, pattern=r"^(percentage|fixed)$"
    )
    due_date: date | None = None
    notes: str | None = None
    is_batchable: bool | None = None

    _not_null = field_validator("description")(refuse_null)


class ReceiptPayRequest(BaseModel):
    payment_method: str = Field(pattern=r"^(cash|bank_transfer|card|direct_debit|stripe_checkout)$")
    payment_date: date | None = None


class ReceiptReturnRequest(BaseModel):
    return_reason: NonBlank(255)
    return_date: date | None = None


class CreditNoteCreate(BaseModel):
    """Request to rectify an issued receipt with a credit note.

    ``amount`` is the gross total to credit and is positive here — the negative
    is a storage detail of the document, not something a caller states. Omitting
    it credits everything not yet credited.
    """

    reason: NonBlank(500)
    amount: Decimal | None = Field(default=None, gt=0)
    notes: str | None = None


class ReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    receipt_number: str
    document_type: str = "invoice"
    rectifies_receipt_id: int | None = None
    member_id: int
    concept_id: int | None
    registration_id: int | None
    remittance_id: int | None
    purchased_membership_type_id: int | None = None
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
    stripe_checkout_session_id: str | None = None
    stripe_payment_intent_id: str | None = None
    refund_amount: Decimal | None = None
    refund_date: date | None = None
    refund_reason: str | None = None
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
    # The rectification link read from whichever end the caller is holding: the
    # document this one corrects, and the credit notes correcting it.
    rectifies_receipt_number: str | None = None
    credit_note_ids: list[int] = []
    credited_amount: Decimal = Decimal("0")


class GenerateMembershipFeesRequest(BaseModel):
    billing_period_start: date
    billing_period_end: date
    emission_date: date
    due_date: date | None = None


# --- SEPA Mandate schemas ---


IBAN_PATTERN = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{4,30}$")


def normalize_pasted_iban(value: object) -> object:
    """An IBAN as pasted, reduced to how it is stored.

    People copy an IBAN in groups of four from a statement or a PDF, and the
    grouping is presentation — the stored value is unbroken and upper-case.
    Runs before the rest, so a correctly typed IBAN is not refused over
    whitespace while the checks below stay strict about a stored value.
    """
    if isinstance(value, str):
        return re.sub(r"\s+", "", value).upper()
    return value


def _check_digits_ok(iban: str) -> bool:
    """The ISO 7064 mod-97 check digits every IBAN carries in positions 3-4.

    Move the first four characters to the end, replace each letter by its
    value in base 36 (A=10 ... Z=35), and the integer that spells is 1 mod 97.
    """
    rearranged = iban[4:] + iban[:4]
    return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1


def validate_iban_format(iban: str) -> bool:
    """IBAN structure *and* check digits.

    The check digits are the point: without them a typo in an account number is
    accepted, stored, and written into a pain.008 file — which the official
    schema also accepts, because its IBAN type is a bare pattern — so the bank
    is the first thing that notices, and it can return the whole batch.

    Strict about case and spacing: this validates an IBAN as stored, not as
    typed. `normalize_pasted_iban` is what turns one into the other.
    """
    if not IBAN_PATTERN.match(iban):
        return False
    return _check_digits_ok(iban)


def refuse_invalid_iban(value: str | None) -> str | None:
    """The field validator both mandate schemas apply after normalisation.

    Lives on the schema so the rule is enforced at the boundary rather than
    only in the service — a pattern on the field and a checksum in the service
    is two rules disagreeing about what an IBAN is.

    Raises `PydanticCustomError` rather than `ValueError` so the 422 carries a
    stable `type` the locale files can key on. A bare `ValueError` reaches the
    administrator as `Value error, Invalid IBAN` — Pydantic's own prefix, in
    English, on a screen that may be running in Catalan (#377). The structural
    check is here too, not a `pattern=` on the field, because a pattern failure
    answers with the regex itself.

    Two codes, because the remedies differ: `malformed_iban` is not shaped like
    an account number at all, `invalid_iban` is shaped right but its check
    digits do not agree with the rest.
    """
    if value is None:
        return value
    if not IBAN_PATTERN.match(value):
        raise PydanticCustomError("malformed_iban", "Not an IBAN")
    if not _check_digits_ok(value):
        raise PydanticCustomError("invalid_iban", "Invalid IBAN")
    return value




class MandateCreate(BaseModel):
    member_id: int
    debtor_name: NonBlank(255)
    debtor_iban: str = Field(min_length=5, max_length=34)
    _clean_iban = field_validator("debtor_iban", mode="before")(normalize_pasted_iban)
    _check_iban = field_validator("debtor_iban")(refuse_invalid_iban)
    debtor_bic: str | None = Field(
        default=None, max_length=11, pattern=r"^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$"
    )
    mandate_type: str = Field(default="recurrent", pattern=r"^(recurrent|one_off)$")
    signature_method: str = Field(default="paper", pattern=r"^(paper|digital)$")
    signed_at: date
    notes: str | None = None


class MandateUpdate(BaseModel):
    debtor_name: NonBlank(255) | None = None
    debtor_iban: str | None = Field(default=None, min_length=5, max_length=34)

    _clean_iban = field_validator("debtor_iban", mode="before")(normalize_pasted_iban)
    _check_iban = field_validator("debtor_iban")(refuse_invalid_iban)
    debtor_bic: str | None = Field(
        default=None, max_length=11, pattern=r"^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$"
    )
    notes: str | None = None

    _not_null = field_validator("debtor_name")(refuse_null)


class DocumentInfo(BaseModel):
    filename: str
    size_bytes: int
    uploaded_at: str


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
    document_info: DocumentInfo | None = None
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
    provider_type: NonBlank(50)
    display_name: NonBlank(255)
    status: str = Field(default="disabled", pattern=r"^(active|test|disabled)$")
    config: dict = Field(default_factory=dict)
    is_default: bool = False


class PaymentProviderUpdate(BaseModel):
    display_name: NonBlank(255) | None = None
    status: str | None = Field(default=None, pattern=r"^(active|test|disabled)$")
    config: dict | None = None
    is_default: bool | None = None

    _not_null = field_validator("display_name")(refuse_null)


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


# --- Billing Run schemas (recurring billing) ---


class RunNowRequest(BaseModel):
    """Admin manual trigger. Omit `frequency` to run every due frequency."""

    frequency: str | None = Field(
        default=None, pattern=r"^(monthly|quarterly|annual)$"
    )


class BillingRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    frequency: str
    period_start: date
    period_end: date
    triggered_by: str
    triggered_by_user_id: int | None = None
    status: str
    receipts_generated: int
    errors: list[dict] = []
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ReceiptReminderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    receipt_id: int
    reminder_number: int
    channel: str
    status: str
    to_email: str | None = None
    triggered_by: str
    triggered_by_user_id: int | None = None
    error: str | None = None
    sent_at: datetime | None = None
    created_at: datetime | None = None


# --- Membership plan purchase schemas ---


class MembershipPurchaseRequest(BaseModel):
    membership_type_id: int


class MembershipPurchaseQuote(BaseModel):
    """What buying a plan costs today, before and after tax.

    ``total_amount`` is the figure to show a member. The stored plan price is a
    base amount and VAT is only added when the receipt is raised, so a portal
    quoting ``base_amount`` alone would show a number the receipt contradicts —
    the tax is computed here, by the same code that raises the receipt, rather
    than reconstructed in the browser from a rate it has no reliable way to read.

    ``months_charged`` / ``months_in_period`` are the prorated fraction of the
    calendar period being paid for, and are null for a ``one_time`` plan, which
    has no period. They are what lets the portal warn that an annual plan bought
    in December is a month of cover, not a year.
    """

    membership_type_id: int
    membership_type_name: str
    billing_frequency: str
    full_price: Decimal
    base_amount: Decimal
    vat_rate: Decimal
    vat_amount: Decimal
    total_amount: Decimal
    is_prorated: bool
    period_start: date | None = None
    period_end: date | None = None
    months_charged: int | None = None
    months_in_period: int | None = None


class MembershipPurchaseResponse(MembershipPurchaseQuote):
    """The quote that was charged, plus the receipt now waiting to be paid.

    ``receipt_id`` is what the portal hands to the existing Stripe or Redsys
    checkout endpoint. The member's plan does not change until that receipt is
    paid.
    """

    receipt_id: int
    receipt_number: str
    receipt_status: str
    due_date: date | None = None
