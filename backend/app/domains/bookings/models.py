"""Simple Bookings models — spaces, dated slots, member bookings.

A ``Space`` is a bookable resource with daily opening hours. A ``SpaceSlot`` is
an admin-defined slot on a **concrete date** with a ``capacity`` (how many
members may hold it at once); slots generated together by a repeat rule share a
``series_id`` so an edit can target one occurrence or the upcoming series. A
``Booking`` is one member holding a slot; when a slot is full a booking is
``waitlisted`` and promoted FIFO on a cancellation.

Capacity is enforced in the service under a row lock, not by an index — a count
is not a uniqueness rule. The partial unique index below only stops a member
holding two active rows for the same slot.
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.domains.activities.models import PAYMENT_FLOW_PAY_TO_CONFIRM


class Space(Base):
    __tablename__ = "spaces"
    __table_args__ = (
        CheckConstraint("close_time > open_time", name="space_hours_valid"),
        CheckConstraint(
            "price IS NULL OR price >= 0", name="space_price_non_negative"
        ),
        CheckConstraint(
            "payment_flow IN ('legacy', 'pay_to_confirm')",
            name="valid_space_payment_flow",
        ),
        CheckConstraint(
            "payment_methods <@ ARRAY['card', 'bizum', 'transfer', 'cash']::varchar[]",
            name="valid_space_payment_methods",
        ),
        Index("ix_spaces_active", "is_active"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    space_type = Column(String(50))
    description = Column(Text)
    # What one booking of this space costs, before VAT. NULL or 0 = free, and a
    # free space raises no receipt at all. A slot may override it.
    price = Column(Numeric(10, 2))
    open_time = Column(Time, nullable=False)
    close_time = Column(Time, nullable=False)
    # Membership type ids allowed to book. Empty or NULL = open to every member,
    # the same reading as Activity.allowed_membership_types.
    allowed_membership_types = Column(ARRAY(Integer))
    # ``legacy`` books at once and bills afterwards; ``pay_to_confirm`` holds a paid
    # booking as pending until its receipt is paid. May be switched from legacy to
    # pay_to_confirm, never back, and only new bookings follow the switch (#603).
    payment_flow = Column(
        String(20),
        nullable=False,
        default=PAYMENT_FLOW_PAY_TO_CONFIRM,
        server_default=PAYMENT_FLOW_PAY_TO_CONFIRM,
    )
    payment_methods = Column(
        ARRAY(String), nullable=False, default=list, server_default="{}"
    )
    # Override of the club's booking auto-cancel default; NULL inherits it.
    auto_cancel_enabled = Column(Boolean)
    auto_cancel_hours = Column(Integer)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    slots = relationship(
        "SpaceSlot", back_populates="space", cascade="all, delete-orphan"
    )


class SpaceSlot(Base):
    __tablename__ = "space_slots"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="space_slot_time_valid"),
        CheckConstraint("capacity >= 1", name="space_slot_capacity_valid"),
        CheckConstraint(
            "price IS NULL OR price >= 0", name="space_slot_price_non_negative"
        ),
        Index("ix_space_slots_space_date", "space_id", "slot_date"),
        Index("ix_space_slots_series", "series_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    space_id = Column(
        Integer, ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False
    )
    slot_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    capacity = Column(SmallInteger, nullable=False, default=1, server_default="1")
    # Overrides the space's price for this one slot — prime time costs more.
    # NULL falls back to the space; 0 is an explicit free slot in a paid space.
    price = Column(Numeric(10, 2))
    # Slots generated together by one repeat rule share a series_id; NULL = one-off.
    series_id = Column(UUID(as_uuid=True))
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    space = relationship("Space", back_populates="slots")
    bookings = relationship(
        "Booking", back_populates="slot", cascade="all, delete-orphan"
    )


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint(
            "status IN ('booked', 'waitlisted', 'cancelled', 'pending')",
            name="booking_status_valid",
        ),
        Index("ix_bookings_slot", "space_slot_id"),
        Index("ix_bookings_party", "party_id"),
        # One active row per party per slot — blocks double-booking and being
        # both booked (or pending) and waitlisted for the same slot.
        Index(
            "uq_bookings_party_slot_active",
            "space_slot_id",
            "party_id",
            unique=True,
            postgresql_where=text("status IN ('booked', 'waitlisted', 'pending')"),
        ),
        CheckConstraint(
            "refund_status IN ('none', 'due', 'returned')",
            name="valid_booking_refund_status",
        ),
        CheckConstraint(
            "cancelled_cause IN ('payment_expired')",
            name="valid_booking_cancelled_cause",
        ),
        Index(
            "idx_bookings_pending_due",
            "payment_due_at",
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    space_slot_id = Column(
        Integer, ForeignKey("space_slots.id", ondelete="CASCADE"), nullable=False
    )
    # Same shape as registrations (ADR 0003, Phase 4): a booking belongs to
    # a party, and member-only spaces are a service-layer rule.
    party_id = Column(
        BigInteger,
        ForeignKey("party.id", ondelete="CASCADE", name="bookings_party_id_fkey"),
        nullable=False,
    )
    status = Column(String(20), nullable=False, default="booked", server_default="booked")
    # Set when a booking enters the waitlist; FIFO promotion orders by this.
    waitlisted_at = Column(DateTime(timezone=True))
    cancelled_at = Column(DateTime(timezone=True))
    cancelled_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    # A pending booking's deadline, always set (#603): the slot's start less the
    # club's cut-off, or earlier when auto-cancel is on. ``pending_since`` is when
    # the hold began, at booking or promotion, which the reminder is timed from.
    payment_due_at = Column(DateTime(timezone=True))
    pending_since = Column(DateTime(timezone=True))
    payment_reminder_sent_at = Column(DateTime(timezone=True))
    # Why the system, not a person, cancelled the booking. NULL otherwise.
    cancelled_cause = Column(String(30))
    # The registration's columns for a payment that arrived after the booking was
    # released, and for money the club owes back on a booking it no longer holds.
    late_payment_at = Column(DateTime(timezone=True))
    late_payment_seen_at = Column(DateTime(timezone=True))
    refund_status = Column(
        String(20), nullable=False, default="none", server_default="none"
    )
    refund_returned_at = Column(DateTime(timezone=True))
    refund_returned_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL", name="fk_bookings_refund_returned_by"),
    )
    refund_credit_note_id = Column(
        Integer,
        ForeignKey(
            "receipts.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_bookings_refund_credit_note_id",
        ),
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    slot = relationship("SpaceSlot", back_populates="bookings")
    party = relationship("Party")
    member = relationship(
        "Member",
        primaryjoin="Booking.party_id == foreign(Member.party_id)",
        order_by="desc(Member.is_active)",
        uselist=False,
        viewonly=True,
    )
    @property
    def member_id(self):
        """Transitional API field (ADR 0003, Phase 4): the row keys on the
        party, but the HTTP contract still speaks members. Resolved through
        the ``member`` join (active membership first); None only for a party
        with no membership, which the surface phase will make routine.
        Read-only on purpose — internal code writes ``party_id``.
        """
        member = self.member
        return member.id if member else None

