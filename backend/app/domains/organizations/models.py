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
    event,
    func,
    insert,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.domains.persons.models import BankAccount, Contact


def _club_party(**values):
    from app.domains.persons.models import Party

    values.setdefault("display_name", "(unnamed)")
    return Party(kind="association", **values)


class OrganizationSettings(Base):
    """Configuration of the instance. The club's identity lives on its party
    (ADR 0003, Phase 5c): name, legal name, tax id, email and logo are party
    columns read and written through the proxies below; phone and website are
    the party's primary contacts; the collection account is the party's
    primary ``bank_accounts`` row. What stays here is what configures this
    deployment — locale, billing counters, the SEPA creditor scheme id,
    branding colour, feature flags.
    """

    __tablename__ = "organization_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="single_organization"),
    )

    id = Column(Integer, primary_key=True)
    party_id = Column(
        BigInteger,
        ForeignKey("party.id", name="organization_settings_party_id_fkey"),
        nullable=False,
        unique=True,
    )
    locale = Column(String(10), default="es")
    timezone = Column(String(50), default="Europe/Madrid")
    currency = Column(String(3), default="EUR")
    date_format = Column(String(20), default="DD/MM/YYYY")
    brand_color = Column(String(7))
    # Invoicing
    invoice_prefix = Column(String(10), default="INV", server_default="INV")
    invoice_next_number = Column(Integer, default=1, server_default="1")
    invoice_annual_reset = Column(Boolean, default=True)
    # Member numbering (v0.7.0 member card) — configurable prefix + zero-padded sequence
    member_number_prefix = Column(String(20), nullable=False, server_default="")
    member_number_padding = Column(SmallInteger, nullable=False, server_default="4")
    member_number_next = Column(Integer, nullable=False, server_default="1")
    default_vat_rate = Column(Numeric(5, 2), default=21.00)
    # SEPA direct debit. The creditor scheme identifier is issued to the
    # organization and is not an account fact, so it stays configuration.
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
    # Writable, so the properties below can append pending rows whose party_id
    # fills from this row's at flush.
    club_contacts = relationship(
        "Contact",
        primaryjoin="OrganizationSettings.party_id == foreign(Contact.party_id)",
        cascade="all, delete-orphan",
        overlaps="party",
    )
    club_bank_accounts = relationship(
        "BankAccount",
        primaryjoin="OrganizationSettings.party_id == foreign(BankAccount.party_id)",
        cascade="all, delete-orphan",
        overlaps="bank_accounts,party",
    )

    # The identity facts, readable and writable as if they were still columns
    # here (they were, until Phase 5c). Same construction as Person's proxies:
    # setting one on a brand-new row creates the pending association party.
    name = association_proxy(
        "party", "display_name",
        creator=lambda value: _club_party(display_name=value or "(unnamed)"),
    )
    legal_name = association_proxy(
        "party", "legal_name",
        creator=lambda value: _club_party(legal_name=value),
    )
    tax_id = association_proxy(
        "party", "national_id",
        creator=lambda value: _club_party(national_id=value),
    )
    email = association_proxy(
        "party", "email",
        creator=lambda value: _club_party(email=value),
    )
    logo_url = association_proxy(
        "party", "photo_url",
        creator=lambda value: _club_party(photo_url=value),
    )

    # --- The club's phone and website: its primary contacts per channel. ---
    # A pending contact has no channel yet (the column follows the type at
    # insert); the hint marks which one it is for, and the Contact insert
    # event resolves a type for that channel.

    def _club_contact(self, channel: str, create: bool = False) -> "Contact | None":
        for contact in self.club_contacts:
            hinted = getattr(contact, "_channel_hint", None)
            if hinted == channel or (hinted is None and contact.channel == channel and contact.is_primary):
                return contact
        if create:
            contact = Contact(value="", is_primary=True)
            contact._channel_hint = channel
            self.club_contacts.append(contact)
            return contact
        return None

    def _get_contact_value(self, channel: str):
        contact = self._club_contact(channel)
        return contact.value or None if contact else None

    def _set_contact_value(self, channel: str, value):
        if not value:
            contact = self._club_contact(channel)
            if contact is not None:
                self.club_contacts.remove(contact)
            return
        self._club_contact(channel, create=True).value = value

    @property
    def phone(self):
        return self._get_contact_value("phone")

    @phone.setter
    def phone(self, value):
        self._set_contact_value("phone", value)

    @property
    def website(self):
        return self._get_contact_value("url")

    @website.setter
    def website(self, value):
        self._set_contact_value("url", value)

    # --- The collection account: the club party's primary bank account. ---

    def _primary_bank_account(self, create: bool = False) -> "BankAccount | None":
        for account in self.club_bank_accounts:
            if account.is_primary:
                return account
        if create:
            account = BankAccount(is_primary=True)
            self.club_bank_accounts.append(account)
            return account
        return None

    @property
    def bank_name(self):
        account = self._primary_bank_account()
        return account.bank_name if account else None

    @bank_name.setter
    def bank_name(self, value):
        if value is None and self._primary_bank_account() is None:
            return
        self._primary_bank_account(create=True).bank_name = value

    @property
    def bank_iban(self):
        account = self._primary_bank_account()
        return account.iban if account else None

    @bank_iban.setter
    def bank_iban(self, value):
        if value is None and self._primary_bank_account() is None:
            return
        self._primary_bank_account(create=True).iban = value

    @property
    def bank_bic(self):
        account = self._primary_bank_account()
        return account.bic if account else None

    @bank_bic.setter
    def bank_bic(self, value):
        if value is None and self._primary_bank_account() is None:
            return
        self._primary_bank_account(create=True).bic = value


# Which contact type backs each club channel. Resolved (and created when
# missing) by the Contact insert event below, so no caller has to know the
# club's phone is a contact row.
CLUB_CONTACT_TYPES = {
    "phone": ("phone_main", "Main Phone"),
    "url": ("website", "Website"),
}


@event.listens_for(Contact, "before_insert")
def _club_contact_resolves_its_type(_mapper, connection, contact):
    """Give a channel-hinted contact a real type (Phase 5c).

    The schema ties ``channel`` to ``contact_type_id`` (NULL together, and the
    composite FK keeps them agreeing), so the club's phone needs a type whose
    channel is ``phone``. The settings properties cannot query for one — they
    run without a session — so they leave a hint and this event, which runs on
    the connection, resolves or creates the type. ``channel`` is set here too:
    ``_contact_carries_its_channel`` registered first (persons imports before
    this module) and already saw the type as missing.
    """
    hint = getattr(contact, "_channel_hint", None)
    if hint is None or contact.contact_type_id is not None:
        return
    from app.domains.persons.models import ContactChannel, ContactType

    code, name = CLUB_CONTACT_TYPES[hint]
    type_id = connection.execute(
        ContactType.__table__.select()
        .with_only_columns(ContactType.__table__.c.id)
        .where(ContactType.__table__.c.code == code)
    ).scalar_one_or_none()
    if type_id is None:
        channel_exists = connection.execute(
            ContactChannel.__table__.select().where(ContactChannel.__table__.c.code == hint)
        ).first()
        if channel_exists is None:
            connection.execute(
                insert(ContactChannel.__table__).values(code=hint, name=name)
            )
        type_id = connection.execute(
            insert(ContactType.__table__)
            .values(code=code, name=name, channel=hint, is_active=True, display_order=0)
            .returning(ContactType.__table__.c.id)
        ).scalar_one()
    contact.contact_type_id = type_id
    contact.channel = hint


@event.listens_for(OrganizationSettings, "before_insert")
def _organization_creates_its_party(_mapper, connection, org):
    """The club's party row, created the same way a person's is.

    Mirrors ``_person_creates_its_party``: the one place every creation path
    (installer, seeder, tests) passes through. Usually the identity proxies
    have already created the pending party and it flushed first; only a bare
    row with no identity at all needs one made here.
    """
    if org.party_id is not None:
        return
    from app.domains.persons.models import Party

    org.party_id = connection.execute(
        insert(Party.__table__)
        .values(kind="association", display_name="(unnamed)")
        .returning(Party.__table__.c.id)
    ).scalar_one()
