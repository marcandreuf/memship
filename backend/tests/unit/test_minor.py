"""Unit tests for minor/guardian logic."""

from datetime import date, timedelta

from app.domains.members.service import MINOR_AGE_THRESHOLD, is_minor_by_dob


class TestIsMinorByDob:
    def test_child_is_minor(self):
        dob = date.today() - timedelta(days=365 * 10)
        assert is_minor_by_dob(dob) is True

    def test_adult_is_not_minor(self):
        dob = date.today() - timedelta(days=365 * 25)
        assert is_minor_by_dob(dob) is False

    def test_exactly_18_is_not_minor(self):
        dob = date.today().replace(year=date.today().year - MINOR_AGE_THRESHOLD)
        assert is_minor_by_dob(dob) is False

    def test_day_before_18_is_minor(self):
        dob = date.today().replace(year=date.today().year - MINOR_AGE_THRESHOLD) + timedelta(days=1)
        assert is_minor_by_dob(dob) is True

    def test_none_dob_is_not_minor(self):
        assert is_minor_by_dob(None) is False
