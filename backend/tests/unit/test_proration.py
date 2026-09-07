"""Unit tests for membership plan proration.

Pure-function tests — no database required.

Proration counts whole months remaining in the calendar period, including the
month of purchase. These tests are deliberately exhaustive: this is arithmetic
about money that a treasurer will check by hand, and it is the one part of the
purchase flow with no user interface to notice a mistake.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.domains.billing.proration import ProratedCharge, prorate_membership_price


class TestTheWorkedExamplesFromTheDesign:
    def test_annual_plan_bought_in_march(self):
        """200 EUR/year on 15 March covers March-December: 10 of 12 months."""
        charge = prorate_membership_price(Decimal("200.00"), "annual", date(2026, 3, 15))
        assert charge.amount == Decimal("166.67")
        assert charge.months_charged == 10
        assert charge.months_in_period == 12
        assert charge.period_start == date(2026, 1, 1)
        assert charge.period_end == date(2026, 12, 31)

    def test_quarterly_plan_bought_in_february(self):
        """50 EUR/quarter on 15 February covers February and March: 2 of 3."""
        charge = prorate_membership_price(Decimal("50.00"), "quarterly", date(2026, 2, 15))
        assert charge.amount == Decimal("33.33")
        assert charge.months_charged == 2
        assert charge.months_in_period == 3
        assert charge.period_start == date(2026, 1, 1)
        assert charge.period_end == date(2026, 3, 31)

    def test_whole_months_not_elapsed_days(self):
        """The day of the month never changes the answer.

        An elapsed-days rule would charge 160.00 for 15 March. Counting whole
        months is what makes the 1st and the 31st cost the same.
        """
        first = prorate_membership_price(Decimal("200.00"), "annual", date(2026, 3, 1))
        last = prorate_membership_price(Decimal("200.00"), "annual", date(2026, 3, 31))
        assert first.amount == last.amount == Decimal("166.67")


class TestMonthly:
    def test_is_never_prorated(self):
        charge = prorate_membership_price(Decimal("25.00"), "monthly", date(2026, 6, 15))
        assert charge.amount == Decimal("25.00")
        assert charge.months_charged == 1
        assert charge.months_in_period == 1

    def test_first_day_of_the_month(self):
        charge = prorate_membership_price(Decimal("25.00"), "monthly", date(2026, 6, 1))
        assert charge.amount == Decimal("25.00")
        assert charge.period_start == date(2026, 6, 1)
        assert charge.period_end == date(2026, 6, 30)

    def test_last_day_of_the_month(self):
        charge = prorate_membership_price(Decimal("25.00"), "monthly", date(2026, 6, 30))
        assert charge.amount == Decimal("25.00")
        assert charge.period_start == date(2026, 6, 1)
        assert charge.period_end == date(2026, 6, 30)

    def test_last_day_of_a_leap_february(self):
        charge = prorate_membership_price(Decimal("25.00"), "monthly", date(2024, 2, 29))
        assert charge.amount == Decimal("25.00")
        assert charge.period_start == date(2024, 2, 1)
        assert charge.period_end == date(2024, 2, 29)


class TestQuarterly:
    @pytest.mark.parametrize(
        "purchase,expected_months,expected_amount,period",
        [
            # Q1
            (date(2026, 1, 1), 3, "60.00", (date(2026, 1, 1), date(2026, 3, 31))),
            (date(2026, 2, 14), 2, "40.00", (date(2026, 1, 1), date(2026, 3, 31))),
            (date(2026, 3, 31), 1, "20.00", (date(2026, 1, 1), date(2026, 3, 31))),
            # Q2
            (date(2026, 4, 1), 3, "60.00", (date(2026, 4, 1), date(2026, 6, 30))),
            (date(2026, 5, 20), 2, "40.00", (date(2026, 4, 1), date(2026, 6, 30))),
            (date(2026, 6, 30), 1, "20.00", (date(2026, 4, 1), date(2026, 6, 30))),
            # Q3
            (date(2026, 7, 1), 3, "60.00", (date(2026, 7, 1), date(2026, 9, 30))),
            (date(2026, 8, 2), 2, "40.00", (date(2026, 7, 1), date(2026, 9, 30))),
            (date(2026, 9, 30), 1, "20.00", (date(2026, 7, 1), date(2026, 9, 30))),
            # Q4
            (date(2026, 10, 1), 3, "60.00", (date(2026, 10, 1), date(2026, 12, 31))),
            (date(2026, 11, 11), 2, "40.00", (date(2026, 10, 1), date(2026, 12, 31))),
            (date(2026, 12, 31), 1, "20.00", (date(2026, 10, 1), date(2026, 12, 31))),
        ],
    )
    def test_every_month_of_every_quarter(
        self, purchase, expected_months, expected_amount, period
    ):
        charge = prorate_membership_price(Decimal("60.00"), "quarterly", purchase)
        assert charge.months_charged == expected_months
        assert charge.months_in_period == 3
        assert charge.amount == Decimal(expected_amount)
        assert (charge.period_start, charge.period_end) == period

    def test_first_month_of_a_quarter_pays_the_full_price(self):
        charge = prorate_membership_price(Decimal("50.00"), "quarterly", date(2026, 7, 3))
        assert charge.amount == Decimal("50.00")
        assert charge.months_charged == charge.months_in_period == 3

    def test_last_month_of_a_quarter_pays_one_third(self):
        charge = prorate_membership_price(Decimal("50.00"), "quarterly", date(2026, 9, 3))
        assert charge.amount == Decimal("16.67")
        assert charge.months_charged == 1

    def test_leap_day_is_an_ordinary_february(self):
        charge = prorate_membership_price(Decimal("60.00"), "quarterly", date(2024, 2, 29))
        assert charge.amount == Decimal("40.00")
        assert charge.months_charged == 2
        assert charge.period_end == date(2024, 3, 31)


class TestAnnual:
    @pytest.mark.parametrize(
        "month,expected_months,expected_amount",
        [
            (1, 12, "240.00"),
            (2, 11, "220.00"),
            (3, 10, "200.00"),
            (4, 9, "180.00"),
            (5, 8, "160.00"),
            (6, 7, "140.00"),
            (7, 6, "120.00"),
            (8, 5, "100.00"),
            (9, 4, "80.00"),
            (10, 3, "60.00"),
            (11, 2, "40.00"),
            (12, 1, "20.00"),
        ],
    )
    def test_every_month_of_the_year(self, month, expected_months, expected_amount):
        charge = prorate_membership_price(
            Decimal("240.00"), "annual", date(2026, month, 10)
        )
        assert charge.months_charged == expected_months
        assert charge.months_in_period == 12
        assert charge.amount == Decimal(expected_amount)
        assert charge.period_start == date(2026, 1, 1)
        assert charge.period_end == date(2026, 12, 31)

    def test_first_day_of_the_year_pays_the_full_price(self):
        charge = prorate_membership_price(Decimal("240.00"), "annual", date(2026, 1, 1))
        assert charge.amount == Decimal("240.00")

    def test_last_day_of_the_year_pays_one_month(self):
        """The December wart, stated as arithmetic.

        Buying an annual plan on 31 December costs one twelfth, and the full
        year lands the following January. That is the calendar-anchored engine
        working as designed, and the purchase UI has to say so.
        """
        charge = prorate_membership_price(Decimal("240.00"), "annual", date(2026, 12, 31))
        assert charge.amount == Decimal("20.00")
        assert charge.months_charged == 1

    def test_leap_day_is_an_ordinary_february(self):
        charge = prorate_membership_price(Decimal("240.00"), "annual", date(2024, 2, 29))
        assert charge.amount == Decimal("220.00")
        assert charge.months_charged == 11
        assert charge.period_end == date(2024, 12, 31)

    def test_a_leap_year_costs_the_same_as_a_common_one(self):
        leap = prorate_membership_price(Decimal("240.00"), "annual", date(2024, 3, 1))
        common = prorate_membership_price(Decimal("240.00"), "annual", date(2026, 3, 1))
        assert leap.amount == common.amount


class TestOneTime:
    """Pay once, hold indefinitely: no proration, no period, no renewal.

    The recurring engine never bills a ``one_time`` plan — ``is_frequency_due``
    is always ``False`` for it — so there is no period to prorate against and
    nothing a later run could double-bill.
    """

    def test_charges_the_full_price(self):
        charge = prorate_membership_price(Decimal("300.00"), "one_time", date(2026, 12, 31))
        assert charge.amount == Decimal("300.00")

    def test_has_no_calendar_period(self):
        charge = prorate_membership_price(Decimal("300.00"), "one_time", date(2026, 3, 15))
        assert charge.period_start is None
        assert charge.period_end is None
        assert charge.months_charged is None
        assert charge.months_in_period is None

    def test_does_not_raise_the_way_compute_period_does(self):
        """``compute_period('one_time', ...)`` raises; this must not."""
        from app.domains.billing.recurring_billing_service import compute_period

        with pytest.raises(ValueError):
            compute_period("one_time", date(2026, 3, 15))

        assert prorate_membership_price(
            Decimal("10.00"), "one_time", date(2026, 3, 15)
        ).amount == Decimal("10.00")

    @pytest.mark.parametrize("day", [date(2026, 1, 1), date(2026, 6, 15), date(2026, 12, 31)])
    def test_the_purchase_date_never_changes_the_price(self, day):
        assert prorate_membership_price(Decimal("300.00"), "one_time", day).amount == (
            Decimal("300.00")
        )


class TestRounding:
    def test_uses_the_shared_half_up_rule(self):
        """An annual plan bought in July is charged exactly half its price.

        100.01 / 2 is 50.005 — the exact half where the old bare ``.quantize``
        would have answered 50.00.
        """
        charge = prorate_membership_price(Decimal("100.01"), "annual", date(2026, 7, 4))
        assert charge.months_charged == 6
        assert charge.amount == Decimal("50.01")

    def test_a_repeating_fraction_is_cut_at_cents(self):
        charge = prorate_membership_price(Decimal("100.00"), "quarterly", date(2026, 2, 1))
        assert charge.amount == Decimal("66.67")

    def test_the_result_always_carries_two_decimals(self):
        charge = prorate_membership_price(Decimal("120"), "annual", date(2026, 1, 1))
        assert str(charge.amount) == "120.00"


class TestDegenerateInputs:
    def test_a_free_plan_costs_nothing(self):
        charge = prorate_membership_price(Decimal("0.00"), "annual", date(2026, 3, 15))
        assert charge.amount == Decimal("0.00")
        assert charge.months_charged == 10

    def test_a_null_price_is_treated_as_free(self):
        """``membership_types.base_price`` is nullable, so this reaches us."""
        charge = prorate_membership_price(None, "annual", date(2026, 3, 15))
        assert charge.amount == Decimal("0.00")

    def test_an_unknown_frequency_is_refused(self):
        with pytest.raises(ValueError, match="Unsupported billing frequency"):
            prorate_membership_price(Decimal("100.00"), "weekly", date(2026, 3, 15))

    def test_the_result_is_immutable(self):
        charge = prorate_membership_price(Decimal("100.00"), "annual", date(2026, 3, 15))
        assert isinstance(charge, ProratedCharge)
        with pytest.raises(Exception):
            charge.amount = Decimal("1.00")
