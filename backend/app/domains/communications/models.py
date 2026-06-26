"""Announcement and Notification models.

``Announcement`` is authored broadcast content (draft → sent). ``Notification``
is the generic per-user in-app surface; announcements are its first producer,
but later features (bookings, convocations) can insert rows with their own
``source_type`` without a schema change.
"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)

from app.db.base import Base


class Announcement(Base):
    __tablename__ = "announcements"
    __table_args__ = (
        CheckConstraint(
            "target_type IN ('all', 'group', 'membership_type')",
            name="valid_announcement_target_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'sent')", name="valid_announcement_status"
        ),
        Index("ix_announcements_status", "status"),
        Index("ix_announcements_created", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)  # simple markdown; rendered sanitized on display
    target_type = Column(String(20), nullable=False)
    # group_id or membership_type_id; NULL when target_type = 'all'
    target_id = Column(Integer)
    status = Column(String(20), nullable=False, default="draft")
    recipient_count = Column(Integer)  # audience size snapshot, set at Send
    sent_at = Column(DateTime(timezone=True))
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('announcement')", name="valid_notification_source_type"
        ),
        # Drives the unread badge count and the list (filter by user_id + read_at).
        Index("ix_notifications_user_unread", "user_id", "read_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source_type = Column(String(30), nullable=False)
    source_id = Column(Integer, nullable=False)
    title = Column(String(200), nullable=False)  # snapshot of subject at send
    excerpt = Column(String(280))  # short body preview for the list
    read_at = Column(DateTime(timezone=True))  # NULL = unread
    created_at = Column(DateTime(timezone=True), server_default=func.now())
