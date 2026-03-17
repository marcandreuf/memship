"""Member and MembershipType models."""

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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class Group(Base):
    __tablename__ = "groups"
    __table_args__ = (
        CheckConstraint("slug ~ '^[a-z0-9-]+$'", name="group_slug_format"),
        Index("idx_groups_slug", "slug"),
        Index("idx_groups_display_order", "display_order"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    slug = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    is_billable = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    color = Column(String(7))
    icon = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    membership_types = relationship("MembershipType", back_populates="group")


class MembershipType(Base):
    __tablename__ = "membership_types"
    __table_args__ = (
        CheckConstraint(
            "billing_frequency IN ('monthly', 'quarterly', 'annual', 'one_time')",
            name="valid_billing_frequency",
        ),
        CheckConstraint("slug ~ '^[a-z0-9-]+$'", name="membership_type_slug_format"),
        Index("idx_membership_types_slug", "slug"),
        Index("idx_membership_types_is_active", "is_active"),
        Index("idx_membership_types_display_order", "display_order"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text)
    slug = Column(String(100), unique=True, nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="SET NULL"))
    min_age = Column(Integer)
    max_age = Column(Integer)
    max_members = Column(Integer)
    current_members = Column(Integer, default=0)
    base_price = Column(Numeric(10, 2), default=0)
    billing_frequency = Column(String(20), default="annual")
    is_fixed_term = Column(Boolean, default=False)
    term_months = Column(Integer)
    benefits = Column(ARRAY(Text))
    custom_fields_schema = Column(JSONB, default=list)
    display_order = Column(Integer, default=0)
    color = Column(String(7))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    group = relationship("Group", back_populates="membership_types")
    members = relationship("Member", back_populates="membership_type")


class Member(Base):
    __tablename__ = "members"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'active', 'suspended', 'cancelled', 'expired')",
            name="valid_status",
        ),
        Index("idx_members_person_id", "person_id"),
        Index("idx_members_user_id", "user_id", postgresql_where="user_id IS NOT NULL"),
        Index("idx_members_membership_type_id", "membership_type_id"),
        Index("idx_members_member_number", "member_number", postgresql_where="member_number IS NOT NULL"),
        Index("idx_members_status", "status"),
        Index("idx_members_is_active", "is_active"),
        Index("idx_members_joined_at", "joined_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    person_id = Column(Integer, ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    membership_type_id = Column(Integer, ForeignKey("membership_types.id", ondelete="SET NULL"))
    member_number = Column(String(50), unique=True)
    status = Column(String(50), default="active")
    status_reason = Column(Text)
    status_changed_at = Column(DateTime(timezone=True), server_default=func.now())
    joined_at = Column(Date, nullable=False, server_default=func.current_date())
    expires_at = Column(Date)
    renewed_at = Column(Date)
    guardian_person_id = Column(Integer, ForeignKey("persons.id", ondelete="SET NULL"))
    is_minor = Column(Boolean, default=False)
    custom_data = Column(JSONB, default=dict)
    communication_preferences = Column(
        JSONB, default=lambda: {"email": True, "sms": False, "push": False}
    )
    internal_notes = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    # Relationships
    person = relationship("Person", back_populates="member", foreign_keys=[person_id])
    user = relationship("User", foreign_keys=[user_id])
    membership_type = relationship("MembershipType", back_populates="members")
    guardian = relationship("Person", foreign_keys=[guardian_person_id])
