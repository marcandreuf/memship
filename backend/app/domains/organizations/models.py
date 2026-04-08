"""Organization settings model — single-tenant, one record per deployment."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


class OrganizationSettings(Base):
    __tablename__ = "organization_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="single_organization"),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    legal_name = Column(String(255))
    email = Column(String(255))
    phone = Column(String(50))
    website = Column(String(255))
    logo_url = Column(String(500))
    tax_id = Column(String(50))
    locale = Column(String(10), default="es")
    timezone = Column(String(50), default="Europe/Madrid")
    currency = Column(String(3), default="EUR")
    date_format = Column(String(20), default="DD/MM/YYYY")
    brand_color = Column(String(7))
    # Banking & invoicing
    bank_name = Column(String(255))
    bank_iban = Column(String(34))
    bank_bic = Column(String(11))
    invoice_prefix = Column(String(10), default="INV")
    invoice_next_number = Column(Integer, default=1)
    invoice_annual_reset = Column(Boolean, default=True)
    default_vat_rate = Column(Numeric(5, 2), default=21.00)
    # SEPA direct debit
    creditor_id = Column(String(35))
    sepa_format = Column(String(20), default="pain.008")
    features = Column(JSONB, default=dict)
    custom_settings = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
