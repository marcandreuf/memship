"""Audit log model."""

from sqlalchemy import (
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
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB

from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint(
            "action IN ('create', 'update', 'delete')",
            name="valid_action",
        ),
        Index("idx_audit_logs_table_record", "table_name", "record_id"),
        Index("idx_audit_logs_user_id", "user_id"),
        Index("idx_audit_logs_created_at", "created_at"),
        Index("idx_audit_logs_action", "action"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    table_name = Column(String(100), nullable=False)
    record_id = Column(Integer, nullable=False)
    action = Column(String(50), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    old_values = Column(JSONB)
    new_values = Column(JSONB)
    changed_fields = Column(ARRAY(Text))
    ip_address = Column(INET)
    user_agent = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
