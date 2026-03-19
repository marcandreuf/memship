"""Activity domain models."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published', 'cancelled', 'completed', 'archived')",
            name="valid_status",
        ),
        CheckConstraint("slug ~ '^[a-z0-9-]+$'", name="activity_slug_format"),
        Index("idx_activities_slug", "slug"),
        Index("idx_activities_status", "status"),
        Index("idx_activities_starts_at", "starts_at"),
        Index("idx_activities_is_active", "is_active"),
        Index("idx_activities_is_featured", "is_featured"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(150), unique=True, nullable=False)
    description = Column(Text)
    short_description = Column(String(500))
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)
    location = Column(String(255))
    location_details = Column(Text)
    location_url = Column(String(500))
    registration_starts_at = Column(DateTime(timezone=True), nullable=False)
    registration_ends_at = Column(DateTime(timezone=True), nullable=False)
    min_participants = Column(Integer, default=0)
    max_participants = Column(Integer, nullable=False)
    current_participants = Column(Integer, default=0)
    waitlist_count = Column(Integer, default=0)
    min_age = Column(Integer)
    max_age = Column(Integer)
    allowed_membership_types = Column(ARRAY(Integer))
    status = Column(String(20), default="draft")
    tax_rate = Column(Numeric(5, 2), default=0)
    image_url = Column(String(500))
    thumbnail_url = Column(String(500))
    features = Column(JSONB, default=dict)
    registration_fields_schema = Column(JSONB, default=list)
    requirements = Column(Text)
    what_to_bring = Column(Text)
    cancellation_policy = Column(Text)
    allow_self_cancellation = Column(Boolean, default=False)
    self_cancellation_deadline_hours = Column(Integer)
    is_active = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))

    # Relationships
    modalities = relationship(
        "ActivityModality", back_populates="activity", lazy="selectin"
    )
    prices = relationship("ActivityPrice", back_populates="activity", lazy="selectin")
    registrations = relationship("Registration", back_populates="activity")
    discount_codes = relationship("DiscountCode", back_populates="activity")
    consents = relationship("ActivityConsent", back_populates="activity")
    attachment_types = relationship("ActivityAttachmentType", back_populates="activity")


class ActivityModality(Base):
    __tablename__ = "activity_modalities"
    __table_args__ = (
        UniqueConstraint("activity_id", "name", name="uq_activity_modality_name"),
        Index("idx_activity_modalities_activity_id", "activity_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_id = Column(
        Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(255), nullable=False)
    description = Column(Text)
    max_participants = Column(Integer)
    current_participants = Column(Integer, default=0)
    registration_deadline = Column(DateTime(timezone=True))
    display_order = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    activity = relationship("Activity", back_populates="modalities")
    prices = relationship(
        "ActivityPrice", back_populates="modality", lazy="selectin"
    )


class ActivityPrice(Base):
    __tablename__ = "activity_prices"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="activity_price_amount_non_negative"),
        Index("idx_activity_prices_activity_id", "activity_id"),
        Index("idx_activity_prices_modality_id", "modality_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_id = Column(
        Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False
    )
    modality_id = Column(
        Integer, ForeignKey("activity_modalities.id", ondelete="SET NULL")
    )
    name = Column(String(255), nullable=False, default="General Price")
    description = Column(Text)
    amount = Column(Numeric(10, 2), nullable=False)
    display_order = Column(Integer, default=1)
    is_optional = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False)
    is_visible = Column(Boolean, default=True)
    max_registrations = Column(Integer)
    current_registrations = Column(Integer, default=0)
    valid_from = Column(DateTime(timezone=True))
    valid_until = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    activity = relationship("Activity", back_populates="prices")
    modality = relationship("ActivityModality", back_populates="prices")


class DiscountCode(Base):
    __tablename__ = "discount_codes"
    __table_args__ = (
        CheckConstraint(
            "discount_type IN ('percentage', 'fixed')",
            name="valid_discount_type",
        ),
        CheckConstraint("discount_value > 0", name="discount_value_positive"),
        CheckConstraint(
            "discount_type != 'percentage' OR discount_value <= 100",
            name="percentage_max_100",
        ),
        UniqueConstraint("activity_id", "code", name="uq_discount_code_per_activity"),
        Index("idx_discount_codes_activity_id", "activity_id"),
        Index("idx_discount_codes_code", "code"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_id = Column(
        Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False
    )
    code = Column(String(50), nullable=False)
    description = Column(Text)
    discount_type = Column(String(20), nullable=False)  # 'percentage' or 'fixed'
    discount_value = Column(Numeric(10, 2), nullable=False)
    max_uses = Column(Integer)  # NULL = unlimited
    current_uses = Column(Integer, default=0)
    valid_from = Column(DateTime(timezone=True))
    valid_until = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    activity = relationship("Activity", back_populates="discount_codes")


class ActivityConsent(Base):
    __tablename__ = "activity_consents"
    __table_args__ = (
        Index("idx_activity_consents_activity_id", "activity_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_id = Column(
        Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False
    )
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    is_mandatory = Column(Boolean, default=True)
    display_order = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    activity = relationship("Activity", back_populates="consents")


class ActivityAttachmentType(Base):
    __tablename__ = "activity_attachment_types"
    __table_args__ = (
        Index("idx_activity_attachment_types_activity_id", "activity_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_id = Column(
        Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(255), nullable=False)
    description = Column(Text)
    allowed_extensions = Column(ARRAY(String), default=list)  # e.g. ['pdf', 'jpg', 'png']
    max_file_size_mb = Column(Integer, default=5)
    is_mandatory = Column(Boolean, default=True)
    display_order = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    activity = relationship("Activity", back_populates="attachment_types")


class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('confirmed', 'waitlist', 'cancelled', 'pending')",
            name="valid_registration_status",
        ),
        Index(
            "uq_registration_active_member",
            "activity_id",
            "member_id",
            unique=True,
            postgresql_where=Column("status") != "cancelled",
        ),
        Index("idx_registrations_activity_id", "activity_id"),
        Index("idx_registrations_member_id", "member_id"),
        Index("idx_registrations_status", "status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_id = Column(
        Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False
    )
    member_id = Column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    modality_id = Column(
        Integer, ForeignKey("activity_modalities.id", ondelete="SET NULL")
    )
    price_id = Column(
        Integer, ForeignKey("activity_prices.id", ondelete="SET NULL")
    )
    discount_code_id = Column(
        Integer, ForeignKey("discount_codes.id", ondelete="SET NULL")
    )
    status = Column(String(20), default="confirmed", nullable=False)
    original_amount = Column(Numeric(10, 2))
    discounted_amount = Column(Numeric(10, 2))
    registration_data = Column(JSONB, default=dict)
    member_notes = Column(Text)
    admin_notes = Column(Text)
    cancelled_at = Column(DateTime(timezone=True))
    cancelled_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    cancelled_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    activity = relationship("Activity", back_populates="registrations")
    member = relationship("Member", foreign_keys=[member_id])
    modality = relationship("ActivityModality")
    price = relationship("ActivityPrice")
    discount_code = relationship("DiscountCode")
    consents = relationship("RegistrationConsent", back_populates="registration")
    attachments = relationship("RegistrationAttachment", back_populates="registration")
    cancelled_by_user = relationship("User", foreign_keys=[cancelled_by], lazy="joined")

    @property
    def cancelled_by_name(self) -> str | None:
        if self.cancelled_by_user is None:
            return None
        person = getattr(self.cancelled_by_user, "person", None)
        if person:
            return f"{person.first_name} {person.last_name}"
        return self.cancelled_by_user.email


class RegistrationConsent(Base):
    __tablename__ = "registration_consents"
    __table_args__ = (
        UniqueConstraint(
            "registration_id", "activity_consent_id",
            name="uq_registration_consent",
        ),
        Index("idx_registration_consents_registration_id", "registration_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    registration_id = Column(
        Integer, ForeignKey("registrations.id", ondelete="CASCADE"), nullable=False
    )
    activity_consent_id = Column(
        Integer, ForeignKey("activity_consents.id", ondelete="CASCADE"), nullable=False
    )
    accepted = Column(Boolean, nullable=False, default=True)
    accepted_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    registration = relationship("Registration", back_populates="consents")
    activity_consent = relationship("ActivityConsent")


class RegistrationAttachment(Base):
    __tablename__ = "registration_attachments"
    __table_args__ = (
        Index("idx_registration_attachments_registration_id", "registration_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    registration_id = Column(
        Integer, ForeignKey("registrations.id", ondelete="CASCADE"), nullable=False
    )
    attachment_type_id = Column(
        Integer, ForeignKey("activity_attachment_types.id", ondelete="SET NULL")
    )
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)  # in bytes
    mime_type = Column(String(100))
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    registration = relationship("Registration", back_populates="attachments")
    attachment_type = relationship("ActivityAttachmentType")
