"""Unit tests for schema validation — no DB required."""

from datetime import date, datetime, timedelta

import pytest

from app.domains.shared.enums import (
    ActivityStatus,
    DiscountType,
    MemberStatus,
    RegistrationStatus,
    UserRole,
)
from app.domains.activities.schemas import (
    ActivityCreate,
    ActivityUpdate,
    ActivityModalityCreate,
    ActivityPriceCreate,
    ActivityPriceUpdate,
)
from app.domains.activities.discount_schemas import (
    DiscountCodeCreate,
    DiscountCodeUpdate,
)
from app.domains.activities.consent_schemas import (
    ActivityConsentCreate,
)
from app.domains.activities.attachment_schemas import (
    ActivityAttachmentTypeCreate,
)
from app.domains.activities.registration_schemas import (
    AdminStatusChangeRequest,
    RegisterRequest,
    CancelRegistrationRequest,
)
from app.domains.members.schemas import (
    MemberCreate,
    MemberUpdate,
    MemberStatusChange,
    MembershipTypeCreate,
    GroupCreate,
    GroupUpdate,
)
from app.domains.organizations.schemas import OrganizationSettingsUpdate


# --- Shared Enums ---


class TestEnums:
    def test_activity_status_values(self):
        assert ActivityStatus.DRAFT == "draft"
        assert ActivityStatus.PUBLISHED == "published"
        assert ActivityStatus.CANCELLED == "cancelled"
        assert ActivityStatus.COMPLETED == "completed"
        assert ActivityStatus.ARCHIVED == "archived"

    def test_member_status_values(self):
        assert MemberStatus.PENDING == "pending"
        assert MemberStatus.ACTIVE == "active"
        assert MemberStatus.SUSPENDED == "suspended"

    def test_registration_status_values(self):
        assert RegistrationStatus.CONFIRMED == "confirmed"
        assert RegistrationStatus.WAITLIST == "waitlist"

    def test_discount_type_values(self):
        assert DiscountType.PERCENTAGE == "percentage"
        assert DiscountType.FIXED == "fixed"

    def test_user_role_values(self):
        assert UserRole.SUPER_ADMIN == "super_admin"
        assert UserRole.MEMBER == "member"


# --- Activity Schemas ---


def _valid_activity_data(**overrides):
    base = {
        "name": "Test Activity",
        "starts_at": "2025-07-01T10:00:00",
        "ends_at": "2025-07-01T18:00:00",
        "registration_starts_at": "2025-06-01T10:00:00",
        "registration_ends_at": "2025-06-30T23:59:00",
        "max_participants": 50,
    }
    base.update(overrides)
    return base


class TestActivityCreate:
    def test_valid(self):
        a = ActivityCreate(**_valid_activity_data())
        assert a.name == "Test Activity"
        assert a.min_participants == 0
        assert a.tax_rate == 0

    def test_ends_before_starts(self):
        with pytest.raises(ValueError, match="ends_at must be after starts_at"):
            ActivityCreate(**_valid_activity_data(ends_at="2025-06-30T10:00:00"))

    def test_reg_ends_before_reg_starts(self):
        with pytest.raises(ValueError, match="registration_ends_at must be after registration_starts_at"):
            ActivityCreate(**_valid_activity_data(
                registration_starts_at="2025-06-30T10:00:00",
                registration_ends_at="2025-06-01T10:00:00",
            ))

    def test_reg_ends_after_starts(self):
        with pytest.raises(ValueError, match="registration_ends_at must be before or equal to starts_at"):
            ActivityCreate(**_valid_activity_data(
                registration_ends_at="2025-07-02T10:00:00",
            ))

    def test_max_age_less_than_min(self):
        with pytest.raises(ValueError, match="max_age must be greater"):
            ActivityCreate(**_valid_activity_data(min_age=18, max_age=10))

    def test_max_participants_less_than_min(self):
        with pytest.raises(ValueError, match="max_participants must be greater"):
            ActivityCreate(**_valid_activity_data(min_participants=100, max_participants=10))

    def test_name_too_long(self):
        with pytest.raises(ValueError):
            ActivityCreate(**_valid_activity_data(name="x" * 256))

    def test_description_max_length(self):
        with pytest.raises(ValueError):
            ActivityCreate(**_valid_activity_data(description="x" * 5001))

    def test_location_details_max_length(self):
        with pytest.raises(ValueError):
            ActivityCreate(**_valid_activity_data(location_details="x" * 2001))

    def test_age_range_bounds(self):
        with pytest.raises(ValueError):
            ActivityCreate(**_valid_activity_data(min_age=-1))

    def test_age_upper_bound(self):
        with pytest.raises(ValueError):
            ActivityCreate(**_valid_activity_data(max_age=121))

    def test_self_cancellation_hours_negative(self):
        with pytest.raises(ValueError):
            ActivityCreate(**_valid_activity_data(self_cancellation_deadline_hours=-1))


class TestActivityUpdate:
    def test_ends_before_starts(self):
        with pytest.raises(ValueError, match="ends_at must be after starts_at"):
            ActivityUpdate(
                starts_at="2025-07-01T10:00:00",
                ends_at="2025-06-30T10:00:00",
            )

    def test_partial_dates_ok(self):
        u = ActivityUpdate(starts_at="2025-07-01T10:00:00")
        assert u.starts_at is not None
        assert u.ends_at is None


# --- Modality Schemas ---


class TestActivityModalityCreate:
    def test_valid(self):
        m = ActivityModalityCreate(name="Morning")
        assert m.display_order == 1

    def test_name_too_long(self):
        with pytest.raises(ValueError):
            ActivityModalityCreate(name="x" * 256)

    def test_description_max_length(self):
        with pytest.raises(ValueError):
            ActivityModalityCreate(name="Test", description="x" * 2001)

    def test_negative_max_participants(self):
        with pytest.raises(ValueError):
            ActivityModalityCreate(name="Test", max_participants=-1)


# --- Price Schemas ---


class TestActivityPriceCreate:
    def test_valid(self):
        p = ActivityPriceCreate(amount=25.0)
        assert p.name == "General Price"

    def test_valid_until_before_from(self):
        with pytest.raises(ValueError, match="valid_until must be after valid_from"):
            ActivityPriceCreate(
                amount=10,
                valid_from="2025-07-01T00:00:00",
                valid_until="2025-06-01T00:00:00",
            )

    def test_negative_amount(self):
        with pytest.raises(ValueError):
            ActivityPriceCreate(amount=-1)


# --- Discount Schemas ---


class TestDiscountCodeCreate:
    def test_valid_percentage(self):
        d = DiscountCodeCreate(code="SAVE10", discount_type="percentage", discount_value=10)
        assert d.discount_type == DiscountType.PERCENTAGE

    def test_valid_fixed(self):
        d = DiscountCodeCreate(code="FLAT5", discount_type="fixed", discount_value=5)
        assert d.discount_type == DiscountType.FIXED

    def test_percentage_over_100(self):
        with pytest.raises(ValueError, match="Percentage discount cannot exceed 100"):
            DiscountCodeCreate(code="X", discount_type="percentage", discount_value=150)

    def test_fixed_over_100_ok(self):
        d = DiscountCodeCreate(code="BIG", discount_type="fixed", discount_value=500)
        assert d.discount_value == 500

    def test_valid_until_before_from(self):
        with pytest.raises(ValueError, match="valid_until must be after valid_from"):
            DiscountCodeCreate(
                code="X",
                discount_type="percentage",
                discount_value=10,
                valid_from="2025-07-01T00:00:00",
                valid_until="2025-06-01T00:00:00",
            )

    def test_code_too_long(self):
        with pytest.raises(ValueError):
            DiscountCodeCreate(code="x" * 51, discount_type="fixed", discount_value=5)

    def test_invalid_discount_type(self):
        with pytest.raises(ValueError):
            DiscountCodeCreate(code="X", discount_type="bogus", discount_value=10)

    def test_description_max_length(self):
        with pytest.raises(ValueError):
            DiscountCodeCreate(code="X", discount_type="fixed", discount_value=5, description="x" * 2001)


# --- Consent Schemas ---


class TestActivityConsentCreate:
    def test_valid(self):
        c = ActivityConsentCreate(title="GDPR", content="You agree...")
        assert c.is_mandatory is True

    def test_content_max_length(self):
        with pytest.raises(ValueError):
            ActivityConsentCreate(title="GDPR", content="x" * 10001)

    def test_content_empty(self):
        with pytest.raises(ValueError):
            ActivityConsentCreate(title="GDPR", content="")


# --- Attachment Schemas ---


class TestActivityAttachmentTypeCreate:
    def test_valid(self):
        a = ActivityAttachmentTypeCreate(name="Photo ID")
        assert a.max_file_size_mb == 5
        assert a.is_mandatory is True

    def test_description_max_length(self):
        with pytest.raises(ValueError):
            ActivityAttachmentTypeCreate(name="X", description="x" * 2001)

    def test_max_file_size_bounds(self):
        with pytest.raises(ValueError):
            ActivityAttachmentTypeCreate(name="X", max_file_size_mb=0)
        with pytest.raises(ValueError):
            ActivityAttachmentTypeCreate(name="X", max_file_size_mb=51)


# --- Registration Schemas ---


class TestAdminStatusChangeRequest:
    def test_valid_enum(self):
        r = AdminStatusChangeRequest(status="confirmed")
        assert r.status == RegistrationStatus.CONFIRMED

    def test_invalid_status(self):
        with pytest.raises(ValueError):
            AdminStatusChangeRequest(status="invalid")

    def test_admin_notes_max_length(self):
        with pytest.raises(ValueError):
            AdminStatusChangeRequest(status="confirmed", admin_notes="x" * 2001)


class TestRegisterRequest:
    def test_discount_code_max_length(self):
        with pytest.raises(ValueError):
            RegisterRequest(price_id=1, discount_code="x" * 51)

    def test_member_notes_max_length(self):
        with pytest.raises(ValueError):
            RegisterRequest(price_id=1, member_notes="x" * 2001)


class TestCancelRegistrationRequest:
    def test_reason_max_length(self):
        with pytest.raises(ValueError):
            CancelRegistrationRequest(reason="x" * 2001)


# --- Member Schemas ---


class TestMemberCreate:
    def test_valid(self):
        m = MemberCreate(first_name="John", last_name="Doe")
        assert m.email is None

    def test_valid_with_email(self):
        m = MemberCreate(first_name="John", last_name="Doe", email="john@example.com")
        assert m.email == "john@example.com"

    def test_invalid_email(self):
        with pytest.raises(ValueError):
            MemberCreate(first_name="John", last_name="Doe", email="not-an-email")

    def test_future_date_of_birth(self):
        with pytest.raises(ValueError, match="future"):
            MemberCreate(
                first_name="John",
                last_name="Doe",
                date_of_birth=date.today() + timedelta(days=1),
            )

    def test_valid_date_of_birth(self):
        m = MemberCreate(first_name="John", last_name="Doe", date_of_birth=date(2000, 1, 1))
        assert m.date_of_birth == date(2000, 1, 1)

    def test_internal_notes_max_length(self):
        with pytest.raises(ValueError):
            MemberCreate(first_name="J", last_name="D", internal_notes="x" * 2001)

    def test_national_id_max_length(self):
        with pytest.raises(ValueError):
            MemberCreate(first_name="J", last_name="D", national_id="x" * 21)


class TestMemberStatusChange:
    def test_valid_enum(self):
        s = MemberStatusChange(status="active")
        assert s.status == MemberStatus.ACTIVE

    def test_invalid_status(self):
        with pytest.raises(ValueError):
            MemberStatusChange(status="nonexistent")

    def test_reason_max_length(self):
        with pytest.raises(ValueError):
            MemberStatusChange(status="active", reason="x" * 2001)


# --- MembershipType Schemas ---


class TestMembershipTypeCreate:
    def test_valid(self):
        t = MembershipTypeCreate(name="Standard", slug="standard")
        assert t.base_price == 0

    def test_invalid_slug(self):
        with pytest.raises(ValueError):
            MembershipTypeCreate(name="Standard", slug="UPPERCASE")

    def test_description_max_length(self):
        with pytest.raises(ValueError):
            MembershipTypeCreate(name="S", slug="s", description="x" * 2001)

    def test_negative_base_price(self):
        with pytest.raises(ValueError):
            MembershipTypeCreate(name="S", slug="s", base_price=-1)


# --- Group Schemas ---


class TestGroupCreate:
    def test_valid(self):
        g = GroupCreate(name="Youth", slug="youth")
        assert g.is_billable is True

    def test_valid_color(self):
        g = GroupCreate(name="Youth", slug="youth", color="#FF6B6B")
        assert g.color == "#FF6B6B"

    def test_invalid_color(self):
        with pytest.raises(ValueError):
            GroupCreate(name="Youth", slug="youth", color="red")

    def test_description_max_length(self):
        with pytest.raises(ValueError):
            GroupCreate(name="Y", slug="y", description="x" * 2001)

    def test_icon_max_length(self):
        with pytest.raises(ValueError):
            GroupCreate(name="Y", slug="y", icon="x" * 51)


class TestGroupUpdate:
    def test_invalid_color(self):
        with pytest.raises(ValueError):
            GroupUpdate(color="notahex")


# --- Organization Schemas ---


class TestOrganizationSettingsUpdate:
    def test_valid(self):
        s = OrganizationSettingsUpdate(name="My Org")
        assert s.name == "My Org"

    def test_valid_email(self):
        s = OrganizationSettingsUpdate(email="org@example.com")
        assert s.email == "org@example.com"

    def test_invalid_email(self):
        with pytest.raises(ValueError):
            OrganizationSettingsUpdate(email="bad")

    def test_invalid_locale(self):
        with pytest.raises(ValueError):
            OrganizationSettingsUpdate(locale="fr")

    def test_valid_locale(self):
        for loc in ["es", "ca", "en"]:
            s = OrganizationSettingsUpdate(locale=loc)
            assert s.locale == loc

    def test_invalid_currency(self):
        with pytest.raises(ValueError):
            OrganizationSettingsUpdate(currency="usd")

    def test_valid_currency(self):
        s = OrganizationSettingsUpdate(currency="EUR")
        assert s.currency == "EUR"

    def test_invalid_brand_color(self):
        with pytest.raises(ValueError):
            OrganizationSettingsUpdate(brand_color="blue")

    def test_valid_brand_color(self):
        s = OrganizationSettingsUpdate(brand_color="#3B82F6")
        assert s.brand_color == "#3B82F6"

    def test_max_lengths(self):
        with pytest.raises(ValueError):
            OrganizationSettingsUpdate(name="x" * 256)
        with pytest.raises(ValueError):
            OrganizationSettingsUpdate(legal_name="x" * 256)
        with pytest.raises(ValueError):
            OrganizationSettingsUpdate(phone="x" * 51)
        with pytest.raises(ValueError):
            OrganizationSettingsUpdate(website="x" * 501)
