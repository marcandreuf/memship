"""Person, Address, and Contact models."""

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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class Person(Base):
    __tablename__ = "persons"
    __table_args__ = (
        Index("idx_persons_email", "email", unique=False, postgresql_where="email IS NOT NULL"),
        Index("idx_persons_last_name", "last_name"),
        Index("idx_persons_national_id", "national_id", postgresql_where="national_id IS NOT NULL"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255))
    date_of_birth = Column(Date)
    gender = Column(String(20))
    national_id = Column(String(50))
    photo_url = Column(String(500))
    bank_iban = Column(String(34))
    bank_bic = Column(String(11))
    custom_fields = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
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
