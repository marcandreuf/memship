"""User model for authentication."""

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
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('super_admin', 'admin', 'member')",
            name="valid_role",
        ),
        Index("idx_users_person_id", "person_id"),
        Index("idx_users_is_active", "is_active"),
        Index("idx_users_reset_token", "reset_token", postgresql_where="reset_token IS NOT NULL"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    person_id = Column(Integer, ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="member")
    permissions = Column(JSONB, default=list)
    email_verified = Column(Boolean, default=False)
    email_verified_at = Column(DateTime(timezone=True))
    last_login_at = Column(DateTime(timezone=True))
    last_login_ip = Column(INET)
    reset_token = Column(String(255))
    reset_token_expires_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    is_locked = Column(Boolean, default=False)
    locked_at = Column(DateTime(timezone=True))
    locked_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    person = relationship("Person", back_populates="user")
