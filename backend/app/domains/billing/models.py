"""Billing domain models — concepts and receipts."""

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
    func,
)
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
            "payment_method IN ('cash', 'bank_transfer', 'card', 'direct_debit') OR payment_method IS NULL",
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
    # remittance_id — column added now, FK constraint deferred to v0.4.0
    remittance_id = Column(Integer)
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
    creator = relationship("User", foreign_keys=[created_by])
