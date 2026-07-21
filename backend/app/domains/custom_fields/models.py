"""Custom profile field models — definition + per-person value (EAV).

Organizations define their own member-profile fields without a code change. A
``CustomFieldDefinition`` is the field itself (type, labels, access); a
``CustomFieldValue`` is one person's answer to it. Values attach to ``persons``
rather than ``members`` because every member is a person, and guardians and
legacy imports are persons too.

Values live in a single ``value`` TEXT column, coerced and validated by the
service against the definition's ``field_type``. That trades indexability for
flexibility — filtering and sorting members by custom-field values needs typed
columns or a GIN index and is deliberately out of scope here.
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
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class CustomFieldDefinition(Base):
    __tablename__ = "custom_field_definitions"
    __table_args__ = (
        CheckConstraint(
            "field_type IN ('text', 'textarea', 'number', 'date', 'boolean', 'select')",
            name="valid_custom_field_type",
        ),
        CheckConstraint(
            "member_access IN ('hidden', 'read', 'write')",
            name="valid_custom_field_member_access",
        ),
        CheckConstraint(
            "admin_access IN ('read', 'write')",
            name="valid_custom_field_admin_access",
        ),
        Index("ix_custom_field_definitions_active_order", "active", "sort_order"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Stable slug used as the API key; immutable after creation.
    key = Column(String(50), nullable=False, unique=True)
    field_type = Column(String(20), nullable=False)
    # Primary-locale label; `labels` holds optional per-locale overrides.
    label = Column(String(100), nullable=False)
    labels = Column(JSONB, nullable=False, default=dict)
    help_text = Column(String(255))
    # For `select`: [{"value": "s", "label": "Small"}, ...]. NULL otherwise.
    options = Column(JSONB)
    required = Column(Boolean, nullable=False, default=False)
    # Who may see/edit this field. Super admin is always write; `restricted`
    # follows admin_access.
    member_access = Column(String(10), nullable=False, default="read")
    admin_access = Column(String(10), nullable=False, default="write")
    sort_order = Column(Integer, nullable=False, default=0)
    # Retire a field without destroying the values already collected.
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    values = relationship(
        "CustomFieldValue",
        back_populates="definition",
        cascade="all, delete-orphan",
    )


class CustomFieldValue(Base):
    __tablename__ = "custom_field_values"
    __table_args__ = (
        UniqueConstraint(
            "definition_id", "person_id", name="uq_custom_field_value_definition_person"
        ),
        Index("ix_custom_field_values_person", "person_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    definition_id = Column(
        Integer,
        ForeignKey("custom_field_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    person_id = Column(
        Integer, ForeignKey("persons.id", ondelete="CASCADE"), nullable=False
    )
    # Canonical string form; coerced per definition.field_type by the service.
    value = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    definition = relationship("CustomFieldDefinition", back_populates="values")
