"""Reminders model — admin notes & dated reminders.

A single flat table backs both concepts: a row with ``due_date`` NULL is a plain
note, a row with a ``due_date`` is a dated reminder. ``is_done`` lets an admin
tick an item off the dashboard rail. Single-tenant, so no ``org_id`` — reminders
are org-wide and visible to every admin.
"""

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
)

from app.db.base import Base


class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (
        Index("ix_reminders_open_due", "is_done", "due_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(Text, nullable=False)
    # NULL → plain note; a date → a dated reminder.
    due_date = Column(Date, nullable=True)
    is_done = Column(Boolean, nullable=False, default=False)
    # Author; nullable so the reminder survives the user's deletion.
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
