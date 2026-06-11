"""Billing domain models — concepts, receipts, mandates, remittances, providers."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class Concept(Base):
    """Billing concept — a type of billable item (membership fee, activity, manual charge)."""

    __tablename__ = "concepts"
    __table_args__ = (
        CheckConstraint(
            "concept_type IN ('membership', 'activity', 'manual', 'service')",
            name="valid_concept_type",
        ),
        CheckConstraint("default_amount >= 0", name="concept_amount_non_negative"),
        CheckConstraint(
            "vat_rate >= 0 AND vat_rate <= 100", name="concept_vat_rate_range"
        ),
        CheckConstraint(
            "default_discount_type IN ('percentage', 'fixed') OR default_discount_type IS NULL",
            name="valid_discount_type",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True)
    description = Column(Text)
    concept_type = Column(String(20), nullable=False)
    default_amount = Column(Numeric(10, 2), default=0, nullable=False)
    vat_rate = Column(Numeric(5, 2), default=21.00, nullable=False)
    default_discount = Column(Numeric(10, 2), default=0)
    default_discount_type = Column(String(20))
    accounting_code = Column(String(50))
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    receipts = relationship("Receipt", back_populates="concept")


class Receipt(Base):
    """Individual billing document — one receipt per concept per member."""

    __tablename__ = "receipts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new', 'pending', 'emitted', 'paid', 'returned', 'cancelled', 'overdue')",
            name="valid_receipt_status",
        ),
        CheckConstraint(
            "origin IN ('membership', 'activity', 'manual', 'service')",
            name="valid_receipt_origin",
        ),
        CheckConstraint(
            "payment_method IN ('cash', 'bank_transfer', 'card', 'direct_debit', 'stripe_checkout', 'redsys', 'bizum') OR payment_method IS NULL",
            name="valid_payment_method",
        ),
        CheckConstraint(
            "discount_type IN ('percentage', 'fixed') OR discount_type IS NULL",
            name="valid_receipt_discount_type",
        ),
        CheckConstraint("base_amount >= 0", name="receipt_base_non_negative"),
        CheckConstraint("vat_rate >= 0 AND vat_rate <= 100", name="receipt_vat_range"),
        CheckConstraint("total_amount >= 0", name="receipt_total_non_negative"),
        Index("ix_receipts_member_id", "member_id"),
        Index("ix_receipts_status", "status"),
        Index("ix_receipts_emission_date", "emission_date"),
        Index("ix_receipts_origin", "origin"),
    )

    id = Column(Integer, primary_key=True, index=True)
    receipt_number = Column(String(50), nullable=False, unique=True)

    # Relationships
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    concept_id = Column(Integer, ForeignKey("concepts.id"))
    registration_id = Column(Integer, ForeignKey("registrations.id"))
    remittance_id = Column(Integer, ForeignKey("remittances.id"))
    created_by = Column(Integer, ForeignKey("users.id"))

    # Origin & description
    origin = Column(String(20), nullable=False)
    description = Column(String(500), nullable=False)

    # Amounts
    base_amount = Column(Numeric(10, 2), nullable=False)
    vat_rate = Column(Numeric(5, 2), nullable=False, default=21.00)
    vat_amount = Column(Numeric(10, 2), nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    discount_amount = Column(Numeric(10, 2), default=0)
    discount_type = Column(String(20))

    # Status & payment
    status = Column(String(20), nullable=False, default="new")
    payment_method = Column(String(20))
    emission_date = Column(Date, nullable=False)
    due_date = Column(Date)
    payment_date = Column(Date)

    # Return/rejection tracking
    return_date = Column(Date)
    return_reason = Column(String(255))

    # Stripe payment tracking
    stripe_checkout_session_id = Column(String(255))
    stripe_payment_intent_id = Column(String(255))

    # Redsys payment tracking
    redsys_ds_order = Column(String(12), unique=True)
    redsys_auth_code = Column(String(8))

    # Refund metadata (manual tracking)
    refund_amount = Column(Numeric(10, 2))
    refund_date = Column(Date)
    refund_reason = Column(String(255))

    # Batch & processor
    is_batchable = Column(Boolean, default=True, nullable=False)
    transaction_id = Column(String(255))

    # Billing period (for recurring fees)
    billing_period_start = Column(Date)
    billing_period_end = Column(Date)

    # Notes
    notes = Column(Text)

    # Soft delete & timestamps
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ORM relationships
    member = relationship("Member", backref="receipts")
    concept = relationship("Concept", back_populates="receipts")
    registration = relationship("Registration", backref="receipts")
    remittance = relationship("Remittance", back_populates="receipts")
    creator = relationship("User", foreign_keys=[created_by])


class SepaMandate(Base):
    """SEPA Direct Debit mandate — member authorization for bank account debiting."""

    __tablename__ = "sepa_mandates"
    __table_args__ = (
        CheckConstraint(
            "mandate_type IN ('recurrent', 'one_off')",
            name="valid_mandate_type",
        ),
        CheckConstraint(
            "signature_method IN ('paper', 'digital')",
            name="valid_signature_method",
        ),
        CheckConstraint(
            "status IN ('active', 'cancelled', 'expired')",
            name="valid_mandate_status",
        ),
        Index("ix_sepa_mandates_member_id", "member_id"),
        Index("ix_sepa_mandates_status", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    mandate_reference = Column(String(35), unique=True, nullable=False)
    creditor_id = Column(String(35), nullable=False)
    debtor_name = Column(String(255), nullable=False)
    debtor_iban = Column(String(34), nullable=False)
    debtor_bic = Column(String(11))
    mandate_type = Column(String(20), nullable=False, default="recurrent")
    signature_method = Column(String(20), nullable=False, default="paper")
    status = Column(String(20), nullable=False, default="active")
    signed_at = Column(Date, nullable=False)
    document_path = Column(String(500))
    cancelled_at = Column(DateTime(timezone=True))
    notes = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ORM relationships
    member = relationship("Member", backref="sepa_mandates")


class Remittance(Base):
    """Payment batch — groups receipts for SEPA direct debit submission."""

    __tablename__ = "remittances"
    __table_args__ = (
        CheckConstraint(
            "remittance_type IN ('sepa')",
            name="valid_remittance_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'ready', 'submitted', 'processed', 'closed', 'cancelled')",
            name="valid_remittance_status",
        ),
        CheckConstraint("total_amount >= 0", name="remittance_total_non_negative"),
        Index("ix_remittances_status", "status"),
        Index("ix_remittances_emission_date", "emission_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    remittance_number = Column(String(50), unique=True, nullable=False)
    remittance_type = Column(String(20), nullable=False, default="sepa")
    status = Column(String(20), nullable=False, default="draft")
    emission_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False, default=0)
    receipt_count = Column(Integer, nullable=False, default=0)
    sepa_file_path = Column(String(500))
    creditor_name = Column(String(255), nullable=False)
    creditor_iban = Column(String(34), nullable=False)
    creditor_bic = Column(String(11))
    creditor_id = Column(String(35), nullable=False)
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ORM relationships
    receipts = relationship("Receipt", back_populates="remittance")
    creator = relationship("User", foreign_keys=[created_by])


class PaymentProvider(Base):
    """Payment provider configuration — stores credentials and settings per provider."""

    __tablename__ = "payment_providers"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'test', 'disabled')",
            name="valid_provider_status",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    provider_type = Column(String(50), nullable=False)
    display_name = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default="disabled")
    config = Column(JSONB, default=dict)
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WebhookEvent(Base):
    """Incoming webhook event — audit log and idempotency dedup."""

    __tablename__ = "webhook_events"
    __table_args__ = (
        CheckConstraint(
            "status IN ('received', 'processed', 'failed', 'ignored')",
            name="valid_webhook_event_status",
        ),
        Index("ix_webhook_events_provider_status", "provider_type", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    provider_type = Column(String(50), nullable=False)
    external_event_id = Column(String(255), unique=True, nullable=False)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSONB, nullable=False)
    status = Column(String(20), nullable=False, default="received")
    error_message = Column(Text)
    receipt_id = Column(Integer, ForeignKey("receipts.id"))
    processed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    receipt = relationship("Receipt")


class BillingRun(Base):
    """Recurring billing run — audit log and idempotency for automatic fee generation.

    One row per (frequency, billing period). The UNIQUE constraint makes the daily
    Celery Beat task idempotent: re-running the same period (duplicate Beat firings,
    or a manual retry on the same day) is rejected at the DB level.
    """

    __tablename__ = "billing_runs"
    __table_args__ = (
        CheckConstraint(
            "frequency IN ('monthly', 'quarterly', 'annual')",
            name="valid_billing_run_frequency",
        ),
        CheckConstraint(
            "triggered_by IN ('scheduled', 'manual')",
            name="valid_billing_run_triggered_by",
        ),
        CheckConstraint(
            "status IN ('success', 'failed', 'partial_failure')",
            name="valid_billing_run_status",
        ),
        UniqueConstraint(
            "frequency",
            "period_start",
            "period_end",
            name="uq_billing_runs_frequency_period",
        ),
        Index("ix_billing_runs_triggered_started", "triggered_by", "started_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    frequency = Column(String(20), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    triggered_by = Column(String(20), nullable=False)
    triggered_by_user_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String(20), nullable=False)
    receipts_generated = Column(Integer, default=0, nullable=False)
    errors = Column(JSONB, default=list, nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ReceiptReminder(Base):
    """Payment reminder sent for an overdue receipt — dunning audit log.

    One row per reminder actually sent (or attempted). The reminder sequence,
    repeat cadence, and max count are enforced by ``reminder_service`` rather than
    a DB constraint, so manual and scheduled sends share a single history and
    ``reminder_number`` is simply ``count(sent reminders) + 1``.
    """

    __tablename__ = "receipt_reminders"
    __table_args__ = (
        CheckConstraint(
            "channel IN ('email')",
            name="valid_receipt_reminder_channel",
        ),
        CheckConstraint(
            "status IN ('sent', 'failed', 'skipped')",
            name="valid_receipt_reminder_status",
        ),
        CheckConstraint(
            "triggered_by IN ('scheduled', 'manual')",
            name="valid_receipt_reminder_triggered_by",
        ),
        Index("ix_receipt_reminders_receipt", "receipt_id", "sent_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id"), nullable=False)
    reminder_number = Column(Integer, nullable=False)
    channel = Column(String(20), nullable=False, default="email")
    status = Column(String(20), nullable=False)
    to_email = Column(String(255))
    triggered_by = Column(String(20), nullable=False)
    triggered_by_user_id = Column(Integer, ForeignKey("users.id"))
    error = Column(Text)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    receipt = relationship("Receipt", backref="reminders")
