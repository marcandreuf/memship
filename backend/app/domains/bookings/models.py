"""Simple Bookings models — spaces, recurring weekly slots, member bookings.

A ``Space`` is a bookable resource with daily opening hours. A ``SpaceSlot`` is
an admin-defined recurring weekly slot on that space with a ``capacity`` (how
many members may hold one slot-instance at once). A ``Booking`` is one member
holding a slot on a concrete date; when a slot-instance is full a booking is
``waitlisted`` and promoted FIFO on a cancellation.

Capacity is enforced in the service under a row lock, not by an index — a count
is not a uniqueness rule. The partial unique index below only stops a member
holding two active rows for the same slot-instance.
"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    Time,
    func,
    text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class Space(Base):
    __tablename__ = "spaces"
    __table_args__ = (
        CheckConstraint("close_time > open_time", name="space_hours_valid"),
        Index("ix_spaces_active", "is_active"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    space_type = Column(String(50))
    description = Column(Text)
    open_time = Column(Time, nullable=False)
    close_time = Column(Time, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
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
        CheckConstraint("weekday BETWEEN 0 AND 6", name="space_slot_weekday_valid"),
        CheckConstraint("end_time > start_time", name="space_slot_time_valid"),
        CheckConstraint("capacity >= 1", name="space_slot_capacity_valid"),
        Index("ix_space_slots_space", "space_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    space_id = Column(
        Integer, ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False
    )
    weekday = Column(SmallInteger, nullable=False)  # 0=Mon … 6=Sun
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    capacity = Column(SmallInteger, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    space = relationship("Space", back_populates="slots")
    bookings = relationship(
        "Booking", back_populates="slot", cascade="all, delete-orphan"
    )


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint(
            "status IN ('booked', 'waitlisted', 'cancelled')",
            name="booking_status_valid",
        ),
        Index("ix_bookings_slot_date", "space_slot_id", "booking_date"),
        Index("ix_bookings_member", "member_id"),
        # One active row per member per slot-instance — blocks double-booking
        # and being both booked and waitlisted for the same instance.
        Index(
            "uq_bookings_member_slot_date_active",
            "space_slot_id",
            "booking_date",
            "member_id",
            unique=True,
            postgresql_where=text("status IN ('booked', 'waitlisted')"),
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    space_slot_id = Column(
        Integer, ForeignKey("space_slots.id", ondelete="CASCADE"), nullable=False
    )
    member_id = Column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    booking_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default="booked")
    # Set when a booking enters the waitlist; FIFO promotion orders by this.
    waitlisted_at = Column(DateTime(timezone=True))
    cancelled_at = Column(DateTime(timezone=True))
    cancelled_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    slot = relationship("SpaceSlot", back_populates="bookings")
    member = relationship("Member")
