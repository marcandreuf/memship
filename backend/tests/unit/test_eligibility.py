"""Unit tests for eligibility checking."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.domains.activities.eligibility import EligibilityResult, _calculate_age, check_eligibility


class TestCalculateAge:
    def test_age_exact_birthday(self):
        assert _calculate_age(date(2000, 6, 15), date(2026, 6, 15)) == 26

    def test_age_before_birthday(self):
        assert _calculate_age(date(2000, 6, 15), date(2026, 6, 14)) == 25

    def test_age_after_birthday(self):
        assert _calculate_age(date(2000, 6, 15), date(2026, 6, 16)) == 26

    def test_age_child(self):
        assert _calculate_age(date(2018, 3, 1), date(2026, 3, 19)) == 8


class TestEligibilityResult:
    def test_starts_eligible(self):
        result = EligibilityResult()
        assert result.eligible is True
        assert result.reasons == []

    def test_add_reason_makes_ineligible(self):
        result = EligibilityResult()
        result.add_reason("Too young")
        assert result.eligible is False
        assert "Too young" in result.reasons

    def test_multiple_reasons(self):
        result = EligibilityResult()
        result.add_reason("Reason 1")
        result.add_reason("Reason 2")
        assert result.eligible is False
        assert len(result.reasons) == 2


def _mock_db(has_existing_registration=False):
    """Create a mock db session."""
    db = MagicMock()
    existing = MagicMock() if has_existing_registration else None
    db.query.return_value.filter.return_value.first.return_value = existing
    return db


def _make_activity(**kwargs):
    now = datetime.now(timezone.utc)
    activity = MagicMock()
    activity.id = 1
    activity.status = kwargs.get("status", "published")
    activity.registration_starts_at = kwargs.get("reg_start", now - timedelta(days=1))
    activity.registration_ends_at = kwargs.get("reg_end", now + timedelta(days=9))
    activity.starts_at = kwargs.get("starts_at", now + timedelta(days=10))
    activity.allowed_membership_types = kwargs.get("allowed_types", None)
    activity.min_age = kwargs.get("min_age", None)
    activity.max_age = kwargs.get("max_age", None)
    return activity


def _make_member(**kwargs):
    member = MagicMock()
    member.id = 1
    member.status = kwargs.get("status", "active")
    member.membership_type_id = kwargs.get("mt_id", 1)
    member.person = MagicMock()
    member.person.date_of_birth = kwargs.get("dob", None)
    return member


class TestCheckEligibility:
    def test_eligible_no_restrictions(self):
        db = _mock_db()
        result = check_eligibility(db, _make_activity(), _make_member())
        assert result.eligible is True

    def test_ineligible_not_published(self):
        db = _mock_db()
        result = check_eligibility(db, _make_activity(status="draft"), _make_member())
        assert result.eligible is False
        assert any("not open" in r for r in result.reasons)

    def test_ineligible_inactive_member(self):
        db = _mock_db()
        result = check_eligibility(db, _make_activity(), _make_member(status="suspended"))
        assert result.eligible is False
        assert any("not active" in r for r in result.reasons)

    def test_ineligible_wrong_membership_type(self):
        db = _mock_db()
        result = check_eligibility(db, _make_activity(allowed_types=[5, 6]), _make_member(mt_id=1))
        assert result.eligible is False
        assert any("Membership type" in r for r in result.reasons)

    def test_ineligible_too_young(self):
        db = _mock_db()
        result = check_eligibility(db, _make_activity(min_age=18), _make_member(dob=date(2018, 1, 1)))
        assert result.eligible is False
        assert any("Minimum age" in r for r in result.reasons)

    def test_ineligible_too_old(self):
        db = _mock_db()
        result = check_eligibility(db, _make_activity(max_age=17), _make_member(dob=date(1990, 1, 1)))
        assert result.eligible is False
        assert any("Maximum age" in r for r in result.reasons)

    def test_ineligible_registration_not_open(self):
        db = _mock_db()
        now = datetime.now(timezone.utc)
        result = check_eligibility(
            db,
            _make_activity(reg_start=now + timedelta(days=5), reg_end=now + timedelta(days=10)),
            _make_member(),
        )
        assert result.eligible is False
        assert any("not opened" in r for r in result.reasons)

    def test_ineligible_registration_closed(self):
        db = _mock_db()
        now = datetime.now(timezone.utc)
        result = check_eligibility(
            db,
            _make_activity(reg_start=now - timedelta(days=10), reg_end=now - timedelta(days=1)),
            _make_member(),
        )
        assert result.eligible is False
        assert any("closed" in r for r in result.reasons)

    def test_ineligible_already_registered(self):
        db = _mock_db(has_existing_registration=True)
        result = check_eligibility(db, _make_activity(), _make_member())
        assert result.eligible is False
        assert any("Already registered" in r for r in result.reasons)
