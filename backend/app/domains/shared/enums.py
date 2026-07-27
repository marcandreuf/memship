"""Shared enums used across domains."""

from enum import StrEnum


class ActivityStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class MemberStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class RegistrationStatus(StrEnum):
    CONFIRMED = "confirmed"
    WAITLIST = "waitlist"
    CANCELLED = "cancelled"
    PENDING = "pending"


class DiscountType(StrEnum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"


class UserRole(StrEnum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    RESTRICTED = "restricted"
    MEMBER = "member"


class CustomFieldType(StrEnum):
    TEXT = "text"
    TEXTAREA = "textarea"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"
    SELECT = "select"


class CustomFieldMemberAccess(StrEnum):
    """What a member may do with their own value of a custom field."""

    HIDDEN = "hidden"
    READ = "read"
    WRITE = "write"


class CustomFieldAdminAccess(StrEnum):
    """What an admin (and restricted) may do with any member's value.

    Admins always read; this only gates writing. Super admin is always write.
    """

    READ = "read"
    WRITE = "write"


class AuthProvider(StrEnum):
    """External identity providers that can be linked to a user."""

    GOOGLE = "google"
    APPLE = "apple"
