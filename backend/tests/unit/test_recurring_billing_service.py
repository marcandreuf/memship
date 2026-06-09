"""Unit tests for recurring billing period computation and due-date logic.

Pure-function tests — no database required.
"""

from datetime import date

import pytest

from app.domains.billing.recurring_billing_service import (
    compute_period,
    is_frequency_due,
)


class TestComputePeriodMonthly:
    def test_mid_month(self):
        assert compute_period("monthly", date(2026, 6, 9)) == (
            date(2026, 6, 1),
            date(2026, 6, 30),
        )

    def test_first_day(self):
        assert compute_period("monthly", date(2026, 1, 1)) == (
            date(2026, 1, 1),
            date(2026, 1, 31),
        )

    def test_last_day(self):
        assert compute_period("monthly", date(2026, 12, 31)) == (
            date(2026, 12, 1),
            date(2026, 12, 31),
        )

    def test_february_leap_year(self):
        assert compute_period("monthly", date(2024, 2, 10)) == (
            date(2024, 2, 1),
            date(2024, 2, 29),
        )

    def test_february_non_leap_year(self):
        assert compute_period("monthly", date(2025, 2, 10)) == (
            date(2025, 2, 1),
            date(2025, 2, 28),
        )


class TestComputePeriodQuarterly:
    @pytest.mark.parametrize(
        "today,expected",
        [
            (date(2026, 1, 1), (date(2026, 1, 1), date(2026, 3, 31))),
            (date(2026, 2, 15), (date(2026, 1, 1), date(2026, 3, 31))),
            (date(2026, 3, 31), (date(2026, 1, 1), date(2026, 3, 31))),
            (date(2026, 4, 1), (date(2026, 4, 1), date(2026, 6, 30))),
            (date(2026, 5, 10), (date(2026, 4, 1), date(2026, 6, 30))),
            (date(2026, 7, 20), (date(2026, 7, 1), date(2026, 9, 30))),
            (date(2026, 10, 5), (date(2026, 10, 1), date(2026, 12, 31))),
            (date(2026, 12, 31), (date(2026, 10, 1), date(2026, 12, 31))),
        ],
    )
    def test_quarter_boundaries(self, today, expected):
        assert compute_period("quarterly", today) == expected


class TestComputePeriodAnnual:
    def test_january(self):
        assert compute_period("annual", date(2026, 1, 1)) == (
            date(2026, 1, 1),
            date(2026, 12, 31),
        )

    def test_mid_year(self):
        assert compute_period("annual", date(2026, 8, 15)) == (
            date(2026, 1, 1),
            date(2026, 12, 31),
        )


class TestComputePeriodInvalid:
    def test_one_time_raises(self):
        with pytest.raises(ValueError):
            compute_period("one_time", date(2026, 6, 9))

    def test_unknown_raises(self):
        with pytest.raises(ValueError):
            compute_period("weekly", date(2026, 6, 9))


class TestIsFrequencyDue:
    def test_monthly_due_on_configured_day(self):
        assert is_frequency_due("monthly", date(2026, 6, 1), billing_day=1) is True
        assert is_frequency_due("monthly", date(2026, 7, 15), billing_day=15) is True

    def test_monthly_not_due_on_wrong_day(self):
        assert is_frequency_due("monthly", date(2026, 6, 2), billing_day=1) is False

    def test_quarterly_due_only_in_quarter_start_months(self):
        # Day matches, first month of a quarter → due
        for month in (1, 4, 7, 10):
            assert is_frequency_due("quarterly", date(2026, month, 1), billing_day=1) is True
        # Day matches but mid-quarter month → not due
        for month in (2, 3, 5, 6, 8, 9, 11, 12):
            assert is_frequency_due("quarterly", date(2026, month, 1), billing_day=1) is False

    def test_quarterly_not_due_on_wrong_day(self):
        assert is_frequency_due("quarterly", date(2026, 1, 2), billing_day=1) is False

    def test_annual_due_only_in_january(self):
        assert is_frequency_due("annual", date(2026, 1, 1), billing_day=1) is True
        assert is_frequency_due("annual", date(2026, 2, 1), billing_day=1) is False

    def test_annual_not_due_on_wrong_day(self):
        assert is_frequency_due("annual", date(2026, 1, 5), billing_day=1) is False

    def test_unknown_frequency_never_due(self):
        assert is_frequency_due("one_time", date(2026, 1, 1), billing_day=1) is False
