"""Organization settings model — single-tenant, one record per deployment."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    event,
    func,
    insert,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class OrganizationSettings(Base):
    __tablename__ = "organization_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="single_organization"),
    )

    id = Column(Integer, primary_key=True)
    # The club is a party like anyone else (ADR 0003, Phase 3): an association
    # with a legal name, a tax number and addresses that work through the same
    # mechanism as everyone else's. This row keeps the configuration; the
    # identity columns below it migrate onto the party in the surface phase.
    party_id = Column(
        BigInteger,
        ForeignKey("party.id", name="organization_settings_party_id_fkey"),
        nullable=False,
        unique=True,
    )
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
    invoice_prefix = Column(String(10), default="INV", server_default="INV")
    invoice_next_number = Column(Integer, default=1, server_default="1")
    invoice_annual_reset = Column(Boolean, default=True)
    # Member numbering (v0.7.0 member card) — configurable prefix + zero-padded sequence
    member_number_prefix = Column(String(20), nullable=False, server_default="")
    member_number_padding = Column(SmallInteger, nullable=False, server_default="4")
    member_number_next = Column(Integer, nullable=False, server_default="1")
    default_vat_rate = Column(Numeric(5, 2), default=21.00)
    # SEPA direct debit
    creditor_id = Column(String(35))
    sepa_format = Column(String(20), default="pain.008")
    features = Column(JSONB, default=dict)
    custom_settings = Column(JSONB, default=dict)
    # SSO provider configuration (Google/Apple) editable from the settings screen.
    # Per-provider node: {"enabled": bool, "<field>": {"value": str, "secret": bool}}.
    # Secret field values are Fernet ciphertext; non-secret are plaintext. Empty
    # fields fall back to the matching env var at resolve time.
    sso_config = Column(JSONB, nullable=False, server_default="{}", default=dict)
    # Mailing provider configuration (Resend/SMTP) editable from the settings
    # screen. Shape: {"active_provider": "resend"|"smtp"|null,
    # "<provider>": {"<field>": {"value": str, "secret": bool}}}. Exactly one
    # provider is active at a time. Secret field values are Fernet ciphertext;
    # empty fields fall back to the matching mail env var at resolve time.
    mailing_config = Column(JSONB, nullable=False, server_default="{}", default=dict)
    # Which outbound email templates are switched on, editable from the settings
    # screen. Shape: {"templates": {"<template_key>": {"enabled": bool}}}. A key
    # that is absent counts as enabled, so an untouched install keeps sending
    # everything. Mandatory templates (see app.domains.mailing.policy) are never
    # stored here — they always send.
    communications_config = Column(JSONB, nullable=False, server_default="{}", default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    party = relationship("Party")


@event.listens_for(OrganizationSettings, "before_insert")
def _organization_creates_its_party(_mapper, connection, org):
    """The club's party row, created the same way a person's is.

    Mirrors ``_person_creates_its_party``: the one place every creation path
    (installer, seeder, tests) passes through. The identity facts are copied
    at creation; they keep living on this row until the surface phase moves
    them, so nothing reads the copies yet.
    """
    if org.party_id is not None:
        return
    from app.domains.persons.models import Party

    org.party_id = connection.execute(
        insert(Party.__table__)
        .values(
            kind="association",
            display_name=(org.name or "").strip() or "(unnamed)",
            national_id=org.tax_id,
            email=org.email,
            photo_url=org.logo_url,
        )
        .returning(Party.__table__.c.id)
    ).scalar_one()
