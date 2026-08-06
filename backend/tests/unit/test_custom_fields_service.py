"""Unit tests for custom profile field value coercion and the access matrix."""

import pytest

from app.domains.custom_fields.models import CustomFieldDefinition
from app.domains.custom_fields.service import (
    TEXTAREA_MAX_LENGTH,
    TEXT_MAX_LENGTH,
    InvalidFieldValue,
    can_read,
    can_write,
    validate_value,
)
from app.core.permissions import ALL_KEYS, MEMBER_SEED_KEYS
from app.domains.shared.enums import (
    CustomFieldAdminAccess,
    CustomFieldMemberAccess,
    CustomFieldType,
)


def make_definition(
    field_type=CustomFieldType.TEXT,
    *,
    key="shirt_size",
    options=None,
    member_access=CustomFieldMemberAccess.READ,
    admin_access=CustomFieldAdminAccess.WRITE,
):
    return CustomFieldDefinition(
        key=key,
        field_type=field_type,
        label="Shirt size",
        options=options,
        member_access=member_access,
        admin_access=admin_access,
    )


class TestValidateValue:
    def test_none_clears_the_field(self):
        assert validate_value(make_definition(), None) is None

    def test_blank_and_whitespace_clear_the_field(self):
        definition = make_definition()
        assert validate_value(definition, "") is None
        assert validate_value(definition, "   ") is None

    def test_text_is_trimmed(self):
        assert validate_value(make_definition(), "  M  ") == "M"

    def test_text_length_cap(self):
        definition = make_definition()
        assert validate_value(definition, "x" * TEXT_MAX_LENGTH)
        with pytest.raises(InvalidFieldValue):
            validate_value(definition, "x" * (TEXT_MAX_LENGTH + 1))

    def test_textarea_has_a_larger_cap(self):
        definition = make_definition(CustomFieldType.TEXTAREA)
        assert validate_value(definition, "x" * TEXTAREA_MAX_LENGTH)
        with pytest.raises(InvalidFieldValue):
            validate_value(definition, "x" * (TEXTAREA_MAX_LENGTH + 1))

    @pytest.mark.parametrize("raw", ["42", "-3", "0.5", 7, 2.5])
    def test_number_accepts_numeric_input(self, raw):
        assert validate_value(make_definition(CustomFieldType.NUMBER), raw) == str(raw)

    @pytest.mark.parametrize("raw", ["abc", "1,5", "12px"])
    def test_number_rejects_non_numeric(self, raw):
        with pytest.raises(InvalidFieldValue):
            validate_value(make_definition(CustomFieldType.NUMBER), raw)

    def test_date_is_normalized_to_iso(self):
        definition = make_definition(CustomFieldType.DATE)
        assert validate_value(definition, "2026-07-21") == "2026-07-21"

    @pytest.mark.parametrize("raw", ["21/07/2026", "2026-13-01", "not a date"])
    def test_date_rejects_bad_input(self, raw):
        with pytest.raises(InvalidFieldValue):
            validate_value(make_definition(CustomFieldType.DATE), raw)

    @pytest.mark.parametrize(
        "raw,expected",
        [(True, "true"), (False, "false"), ("true", "true"), ("FALSE", "false")],
    )
    def test_boolean_is_normalized(self, raw, expected):
        definition = make_definition(CustomFieldType.BOOLEAN)
        assert validate_value(definition, raw) == expected

    def test_boolean_rejects_other_values(self):
        with pytest.raises(InvalidFieldValue):
            validate_value(make_definition(CustomFieldType.BOOLEAN), "yes")

    def test_select_accepts_a_defined_option(self):
        definition = make_definition(
            CustomFieldType.SELECT,
            options=[{"value": "s", "label": "Small"}, {"value": "m", "label": "Medium"}],
        )
        assert validate_value(definition, "m") == "m"

    def test_select_rejects_an_undefined_option(self):
        definition = make_definition(
            CustomFieldType.SELECT, options=[{"value": "s", "label": "Small"}]
        )
        with pytest.raises(InvalidFieldValue) as exc:
            validate_value(definition, "xl")
        assert exc.value.key == "shirt_size"

    def test_error_carries_the_field_key(self):
        with pytest.raises(InvalidFieldValue) as exc:
            validate_value(make_definition(CustomFieldType.NUMBER, key="licence"), "abc")
        assert exc.value.key == "licence"


SCHEMA_EDITOR = frozenset(ALL_KEYS)
STAFF = frozenset({"members.read", "members.write"} | MEMBER_SEED_KEYS)
MEMBER = frozenset(MEMBER_SEED_KEYS)


class TestAccessMatrix:
    """A schema editor always writes; staff read but write only when allowed;
    a self-service account sees and edits only its own record, per member_access."""

    @pytest.mark.parametrize("member_access", list(CustomFieldMemberAccess))
    @pytest.mark.parametrize("admin_access", list(CustomFieldAdminAccess))
    def test_schema_editor_always_reads_and_writes(self, member_access, admin_access):
        definition = make_definition(
            member_access=member_access, admin_access=admin_access
        )
        assert can_read(definition, permissions=SCHEMA_EDITOR, is_own=False)
        assert can_write(definition, permissions=SCHEMA_EDITOR, is_own=False)

    @pytest.mark.parametrize("member_access", list(CustomFieldMemberAccess))
    def test_staff_always_read_regardless_of_member_access(self, member_access):
        definition = make_definition(member_access=member_access)
        assert can_read(definition, permissions=STAFF, is_own=False)

    def test_staff_write_follows_admin_access(self):
        writable = make_definition(admin_access=CustomFieldAdminAccess.WRITE)
        read_only = make_definition(admin_access=CustomFieldAdminAccess.READ)
        assert can_write(writable, permissions=STAFF, is_own=False)
        assert not can_write(read_only, permissions=STAFF, is_own=False)

    def test_member_hidden_field_is_invisible(self):
        definition = make_definition(member_access=CustomFieldMemberAccess.HIDDEN)
        assert not can_read(definition, permissions=MEMBER, is_own=True)
        assert not can_write(definition, permissions=MEMBER, is_own=True)

    def test_member_read_field_is_visible_but_not_writable(self):
        definition = make_definition(member_access=CustomFieldMemberAccess.READ)
        assert can_read(definition, permissions=MEMBER, is_own=True)
        assert not can_write(definition, permissions=MEMBER, is_own=True)

    def test_member_write_field_is_both(self):
        definition = make_definition(member_access=CustomFieldMemberAccess.WRITE)
        assert can_read(definition, permissions=MEMBER, is_own=True)
        assert can_write(definition, permissions=MEMBER, is_own=True)

    @pytest.mark.parametrize("member_access", list(CustomFieldMemberAccess))
    def test_member_gets_nothing_on_another_persons_record(self, member_access):
        definition = make_definition(member_access=member_access)
        assert not can_read(definition, permissions=MEMBER, is_own=False)
        assert not can_write(definition, permissions=MEMBER, is_own=False)

    def test_holding_no_permissions_is_denied(self):
        definition = make_definition(member_access=CustomFieldMemberAccess.WRITE)
        assert not can_read(definition, permissions=frozenset(), is_own=True)
        assert not can_write(definition, permissions=frozenset(), is_own=True)
