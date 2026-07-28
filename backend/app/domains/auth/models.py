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
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('super_admin', 'admin', 'restricted', 'member')",
            name="valid_role",
        ),
        Index("idx_users_person_id", "person_id"),
        Index("idx_users_is_active", "is_active"),
        Index("idx_users_reset_token", "reset_token", postgresql_where="reset_token IS NOT NULL"),
        Index(
            "idx_users_verification_token",
            "verification_token",
            postgresql_where="verification_token IS NOT NULL",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    person_id = Column(Integer, ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    # Nullable: SSO-only users (Google/Apple) have no password. The password login
    # path rejects a user whose hash is NULL.
    password_hash = Column(String(255))
    role = Column(String(50), nullable=False, default="member")
    permissions = Column(JSONB, default=list)
    email_verified = Column(Boolean, default=False)
    email_verified_at = Column(DateTime(timezone=True))
    last_login_at = Column(DateTime(timezone=True))
    last_login_ip = Column(INET)
    reset_token = Column(String(255))
    reset_token_expires_at = Column(DateTime(timezone=True))
    verification_token = Column(String(255))
    verification_token_expires_at = Column(DateTime(timezone=True))
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
    identities = relationship(
        "UserIdentity", back_populates="user", cascade="all, delete-orphan"
    )


class UserIdentity(Base):
    """A external provider account (Google, Apple) linked to a memship user.

    One user can have several identities plus a password, so signing in with
    Google and later with Apple on the same verified email resolves to the same
    account instead of creating a duplicate.
    """

    __tablename__ = "user_identities"
    __table_args__ = (
        CheckConstraint("provider IN ('google', 'apple')", name="valid_auth_provider"),
        UniqueConstraint("provider", "provider_subject", name="uq_provider_subject"),
        Index("idx_user_identities_user_id", "user_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(20), nullable=False)
    # The provider's stable subject id — never the email, which can change.
    provider_subject = Column(String(255), nullable=False)
    email = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="identities")
