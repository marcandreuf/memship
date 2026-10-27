"""Party, Person, Address, and Contact models."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
    insert,
)
from sqlalchemy.orm import relationship, validates

from app.core.schema_types import normalize_email
from app.db.base import Base




class PartyKind(Base):
    """Registry of party kinds — adding one is an INSERT, not a constraint rewrite."""

    __tablename__ = "party_kinds"

    code = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    # Is there a natural person behind this kind? Decides whether a date of
    # birth, a guardian or an age band mean anything.
    is_natural = Column(Boolean, nullable=False, server_default="false")
    display_order = Column(Integer, nullable=False, server_default="0")


class Party(Base):
    """The identity root: anyone the organisation holds a record of (ADR 0003).

    Plumbing, not a product concept — it has no screen of its own. ``persons``
    is its first subtype; a company is a party with ``kind='company'`` and no
    subtype row at all, which is what lets a donation be recorded without
    inventing a member. ``UNIQUE (id, kind)`` is the target of the subtypes'
    composite foreign keys: together with each subtype's pinned ``kind`` it
    makes subtypes mutually exclusive in the database.
    """

    __tablename__ = "party"
    __table_args__ = (
        UniqueConstraint("id", "kind", name="party_id_kind_key"),
        Index("ix_party_kind", "kind"),
        Index("ix_party_display_name", "display_name"),
        Index("ix_party_national_id", "national_id", postgresql_where="national_id IS NOT NULL"),
        Index("ix_party_email", "email", postgresql_where="email IS NOT NULL"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    kind = Column(Text, ForeignKey("party_kinds.code", name="party_kind_fkey"), nullable=False)
    # Maintained from the subtype. The one denormalisation worth taking: every
    # list, receipt PDF and SEPA file wants a name and should not care what
    # kind of party it is. ``sepa_mandates.debtor_name`` set the precedent.
    display_name = Column(Text, nullable=False)
    # Party-level facts: a company has all of these too. They still also live
    # on ``persons`` until the columns move in a later phase; this copy is
    # written at creation and nothing reads it yet.
    national_id = Column(String(50))
    email = Column(String(255))
    photo_url = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Person(Base):
    __tablename__ = "persons"
    __table_args__ = (
        # The composite FK plus the pinned ``kind`` is what makes subtypes
        # mutually exclusive: a persons row can only attach to a party whose
        # kind is 'person', so no party can ever hold two different subtypes.
        ForeignKeyConstraint(
            ["party_id", "kind"],
            ["party.id", "party.kind"],
            name="persons_party_fk",
            ondelete="CASCADE",
        ),
        UniqueConstraint("party_id", name="uq_persons_party_id"),
        CheckConstraint("kind = 'person'", name="persons_kind_check"),
        Index("idx_persons_email", "email", unique=False, postgresql_where="email IS NOT NULL"),
        Index("idx_persons_last_name", "last_name"),
        Index("idx_persons_national_id", "national_id", postgresql_where="national_id IS NOT NULL"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    party_id = Column(BigInteger, nullable=False)
    # Holds no information (always 'person') — it exists so the foreign key
    # above can be composite. See Party.
    kind = Column(Text, nullable=False, server_default="person")
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255))
    date_of_birth = Column(Date)
    gender = Column(String(20))
    national_id = Column(String(50))
    photo_url = Column(String(500))
    bank_iban = Column(String(34))
    bank_bic = Column(String(11))
    bank_holder_name = Column(String(255))
    payment_method = Column(String(20))
    stripe_customer_id = Column(String(255), unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    party = relationship("Party")
    user = relationship("User", back_populates="person", uselist=False)
    member = relationship("Member", back_populates="person", uselist=False, foreign_keys="Member.person_id")
    addresses = relationship(
        "Address",
        back_populates="person",
        primaryjoin="and_(Address.entity_type=='person', Address.entity_id==Person.id)",
        foreign_keys="Address.entity_id",
        viewonly=True,
    )
    contacts = relationship(
        "Contact",
        back_populates="person",
        primaryjoin="and_(Contact.entity_type=='person', Contact.entity_id==Person.id)",
        foreign_keys="Contact.entity_id",
        viewonly=True,
    )

    @validates("email")
    def _normalise_email(self, _key, value):
        """Same rule as ``User.email`` — see the validator there (#191).

        This column is deliberately not unique (a minor shares a guardian's
        address), so normalising it changes no constraint. It is here because
        `attach_login` copies it into ``users.email``, where it decides a login.
        """
        return normalize_email(value)


@event.listens_for(Person, "before_insert")
def _person_creates_its_party(_mapper, connection, person):
    """Every new person gets a party row — the supertype half of ADR 0003.

    An ORM event rather than service code because persons are created in six
    application call sites and across the test suite; this is the one place
    they all pass through. ``party.display_name`` is written here and then
    maintained by a database trigger from the repointing phase onwards; until
    that phase nothing reads it, so a renamed person leaving it briefly stale
    changes no behaviour.
    """
    if person.party_id is not None:
        return
    display_name = " ".join(
        part
        for part in ((person.first_name or "").strip(), (person.last_name or "").strip())
        if part
    )
    person.party_id = connection.execute(
        insert(Party.__table__)
        .values(
            kind="person",
            display_name=display_name or "(unnamed)",
            national_id=person.national_id,
            email=person.email,
            photo_url=person.photo_url,
        )
        .returning(Party.__table__.c.id)
    ).scalar_one()


class AddressType(Base):
    __tablename__ = "address_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), nullable=False, unique=True)
    name = Column(String(50), nullable=False)
    description = Column(String(255))
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Address(Base):
    __tablename__ = "addresses"
    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('person', 'organization', 'space')",
            name="valid_entity_type",
        ),
        Index("idx_addresses_entity", "entity_type", "entity_id"),
        Index("idx_addresses_type", "address_type_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    address_type_id = Column(Integer, ForeignKey("address_types.id", ondelete="SET NULL"))
    entity_type = Column(String(30), nullable=False)
    entity_id = Column(Integer, nullable=False)
    address_line1 = Column(String(255), nullable=False)
    address_line2 = Column(String(255))
    city = Column(String(100), nullable=False)
    state_province = Column(String(100))
    postal_code = Column(String(20))
    country = Column(String(3), default="ES")
    latitude = Column(Numeric(10, 7))
    longitude = Column(Numeric(10, 7))
    is_primary = Column(Boolean, default=False)
    display_order = Column(Integer, default=0)
    label = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    address_type = relationship("AddressType")
    person = relationship(
        "Person",
        back_populates="addresses",
        primaryjoin="and_(Address.entity_type=='person', Address.entity_id==Person.id)",
        foreign_keys=[entity_id],
        viewonly=True,
    )


class ContactType(Base):
    __tablename__ = "contact_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), nullable=False, unique=True)
    name = Column(String(50), nullable=False)
    description = Column(String(255))
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('person')",
            name="valid_contact_entity_type",
        ),
        Index("idx_contacts_entity", "entity_type", "entity_id"),
        Index("idx_contacts_type", "contact_type_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    contact_type_id = Column(Integer, ForeignKey("contact_types.id", ondelete="SET NULL"))
    entity_type = Column(String(30), nullable=False)
    entity_id = Column(Integer, nullable=False)
    value = Column(String(255), nullable=False)
    label = Column(String(100))
    is_primary = Column(Boolean, default=False)
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    contact_type = relationship("ContactType")
    person = relationship(
        "Person",
        back_populates="contacts",
        primaryjoin="and_(Contact.entity_type=='person', Contact.entity_id==Person.id)",
        foreign_keys=[entity_id],
        viewonly=True,
    )
