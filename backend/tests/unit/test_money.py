"""Unit tests for the shared money rounding rule.

Pure-function tests — no database required.

The point of every exact-half case below is that ``ROUND_HALF_EVEN``, the
default the decimal context hands to a bare ``.quantize``, would answer
differently. That divergence was the defect: billing rounded one way and
discounts the other, so a discounted registration could contradict the receipt
raised from it.
"""

import decimal
from decimal import ROUND_HALF_EVEN, Decimal

import pytest

from app.core.money import round_money


class TestRoundMoney:
    def test_rounds_up_on_an_exact_half(self):
        assert round_money(Decimal("1.005")) == Decimal("1.01")

    def test_exact_half_does_not_round_to_even(self):
        """The case where the two rules disagree: half-even would give 1.02."""
        assert round_money(Decimal("1.025")) == Decimal("1.03")
        assert Decimal("1.025").quantize(
            Decimal("0.01"), rounding=ROUND_HALF_EVEN
        ) == Decimal("1.02")

    def test_rounds_down_below_a_half(self):
        assert round_money(Decimal("1.004")) == Decimal("1.00")

    def test_rounds_up_above_a_half(self):
        assert round_money(Decimal("1.006")) == Decimal("1.01")

    def test_negative_exact_half_rounds_away_from_zero(self):
        assert round_money(Decimal("-1.005")) == Decimal("-1.01")

    def test_already_two_decimals_is_unchanged(self):
        assert round_money(Decimal("42.42")) == Decimal("42.42")

    def test_result_always_carries_two_decimal_places(self):
        assert str(round_money(Decimal("5"))) == "5.00"
        assert str(round_money(Decimal("5.1"))) == "5.10"

    def test_zero(self):
        assert round_money(Decimal("0")) == Decimal("0.00")

    def test_a_repeating_division_is_truncated_to_cents(self):
        assert round_money(Decimal("200") * 10 / 12) == Decimal("166.67")

    def test_ignores_the_ambient_decimal_context_rounding(self):
        """A caller's context must not be able to change the answer.

        This is the whole reason the rule is passed explicitly rather than
        inherited: the context is process-wide, mutable and invisible at the
        call site.
        """
        with decimal.localcontext() as ctx:
            ctx.rounding = ROUND_HALF_EVEN
            assert round_money(Decimal("1.025")) == Decimal("1.03")


class TestCallSitesShareTheRule:
    """The three money paths that were split across two rounding modes."""

    def test_vat_uses_half_up(self):
        from app.domains.billing.service import calculate_vat

        # 10.05 EUR at 10% VAT is exactly 1.005.
        vat_amount, total = calculate_vat(Decimal("10.05"), Decimal("10"))
        assert vat_amount == Decimal("1.01")
        assert total == Decimal("11.06")

    def test_percentage_discount_uses_half_up(self):
        from types import SimpleNamespace

        from app.domains.activities.discount_service import apply_discount

        # 10.05 less 10% is 9.045 — an exact half that half-even sends to 9.04.
        discount = SimpleNamespace(discount_type="percentage", discount_value=Decimal("10"))
        assert apply_discount(Decimal("10.05"), discount) == Decimal("9.05")

    def test_discount_still_clamps_at_zero(self):
        from types import SimpleNamespace

        from app.domains.activities.discount_service import apply_discount

        discount = SimpleNamespace(discount_type="fixed", discount_value=Decimal("50"))
        assert apply_discount(Decimal("10.00"), discount) == Decimal("0")


@pytest.mark.parametrize(
    "amount,expected",
    [
        ("0.005", "0.01"),
        ("0.015", "0.02"),
        ("0.025", "0.03"),
        ("0.035", "0.04"),
        ("0.045", "0.05"),
    ],
)
def test_every_exact_half_rounds_up(amount, expected):
    """Half-even would alternate down/up across this sequence."""
    assert round_money(Decimal(amount)) == Decimal(expected)
