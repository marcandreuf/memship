"""The donation origin, and the VAT default that goes with it (#432).

A donation used to go in as ``manual`` beside every other hand-made charge,
with nothing but free text in ``description`` telling them apart. The quieter
half was the rate: both create schemas default ``vat_rate`` to 21.00, which is
right for a taxable supply and wrong for a gift, so an administrator who built
a reusable "Donation" concept got 21% on every donation until somebody noticed.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domains.billing.models import NON_DEBT_ORIGINS
from app.domains.billing.schemas import ConceptCreate, ReceiptCreate


def _receipt(**overrides):
    data = {
        "party_id": 1,
        "origin": "manual",
        "description": "Something",
        "base_amount": Decimal("100.00"),
        "emission_date": "2026-11-05",
    }
    return ReceiptCreate(**{**data, **overrides})


def _concept(**overrides):
    data = {"name": "Something", "concept_type": "manual"}
    return ConceptCreate(**{**data, **overrides})


class TestTheOriginIsAccepted:
    def test_receipt_accepts_donation(self):
        assert _receipt(origin="donation").origin == "donation"

    def test_concept_accepts_donation(self):
        assert _concept(concept_type="donation").concept_type == "donation"

    def test_an_unknown_origin_is_still_refused(self):
        """The pattern was widened, not opened."""
        with pytest.raises(ValidationError):
            _receipt(origin="gift")


class TestDonationVatDefaultsToZero:
    def test_receipt_donation_defaults_to_zero(self):
        assert _receipt(origin="donation").vat_rate == Decimal(0)

    def test_concept_donation_defaults_to_zero(self):
        assert _concept(concept_type="donation").vat_rate == Decimal(0)

    def test_every_other_origin_still_defaults_to_21(self):
        """The control. A default that moved for everything would pass the two
        tests above and silently stop charging VAT on real supplies."""
        assert _receipt(origin="manual").vat_rate == Decimal("21.00")
        assert _concept(concept_type="membership").vat_rate == Decimal("21.00")

    def test_an_explicit_rate_wins_on_a_donation(self):
        """A donation carrying a counterpart can be taxable, so the decision was
        to move the default rather than forbid the value."""
        assert _receipt(origin="donation", vat_rate=Decimal("21.00")).vat_rate == Decimal("21.00")
        assert _concept(concept_type="donation", vat_rate=Decimal("10")).vat_rate == Decimal("10")

    def test_an_explicit_zero_on_a_normal_origin_is_untouched(self):
        assert _receipt(origin="manual", vat_rate=Decimal(0)).vat_rate == Decimal(0)


class TestNonDebtOrigins:
    def test_donation_is_the_only_one(self):
        """Pins the set. Adding an origin here silently removes it from the
        dunning run and from the outstanding figure, which is a decision rather
        than a detail."""
        assert NON_DEBT_ORIGINS == ("donation",)
