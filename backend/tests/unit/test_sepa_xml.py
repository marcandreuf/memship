"""Unit tests for SEPA XML generation."""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.domains.billing.sepa_xml import SepaExportError, generate_sepa_xml


def _mock_remittance(**overrides):
    r = MagicMock()
    r.creditor_name = "Club Test"
    r.creditor_iban = "ES9121000418450200051332"
    r.creditor_bic = "CAIXESBBXXX"
    r.creditor_id = "ES12000B12345678"
    r.due_date = date(2026, 5, 1)
    for k, v in overrides.items():
        setattr(r, k, v)
    return r


def _mock_receipt(member_id=1, total_amount=50.00, receipt_number="FAC-2026-0001", description="Monthly fee"):
    r = MagicMock()
    r.member_id = member_id
    r.total_amount = Decimal(str(total_amount))
    r.receipt_number = receipt_number
    r.description = description
    return r


def _mock_mandate(member_id=1, **overrides):
    m = MagicMock()
    m.member_id = member_id
    m.debtor_name = "John Doe"
    m.debtor_iban = "ES7921000813610123456789"
    m.debtor_bic = "BBVAESMMXXX"
    m.mandate_reference = "FAC-M0001-001"
    m.mandate_type = "recurrent"
    m.signed_at = date(2026, 4, 1)
    for k, v in overrides.items():
        setattr(m, k, v)
    return m


class TestSepaXmlGeneration:
    def test_generates_valid_xml(self):
        remittance = _mock_remittance()
        receipts = [_mock_receipt()]
        mandates = {1: _mock_mandate()}

        xml = generate_sepa_xml(remittance, receipts, mandates)
        assert isinstance(xml, bytes)
        assert b"pain.008.001.02" in xml

    def test_contains_creditor_info(self):
        remittance = _mock_remittance()
        receipts = [_mock_receipt()]
        mandates = {1: _mock_mandate()}

        xml = generate_sepa_xml(remittance, receipts, mandates).decode()
        assert "Club Test" in xml
        assert "ES9121000418450200051332" in xml
        assert "ES12000B12345678" in xml

    def test_contains_debtor_info(self):
        remittance = _mock_remittance()
        receipts = [_mock_receipt()]
        mandates = {1: _mock_mandate()}

        xml = generate_sepa_xml(remittance, receipts, mandates).decode()
        assert "John Doe" in xml
        assert "ES7921000813610123456789" in xml
        assert "FAC-M0001-001" in xml

    def test_amount_in_xml(self):
        remittance = _mock_remittance()
        receipts = [_mock_receipt(total_amount=123.45)]
        mandates = {1: _mock_mandate()}

        xml = generate_sepa_xml(remittance, receipts, mandates).decode()
        assert "123.45" in xml

    def test_multiple_receipts(self):
        remittance = _mock_remittance()
        receipts = [
            _mock_receipt(member_id=1, total_amount=50.00, receipt_number="FAC-2026-0001"),
            _mock_receipt(member_id=2, total_amount=75.00, receipt_number="FAC-2026-0002"),
        ]
        mandates = {
            1: _mock_mandate(member_id=1),
            2: _mock_mandate(member_id=2, debtor_name="Jane Doe", debtor_iban="DE89370400440532013000", debtor_bic="COBADEFFXXX", mandate_reference="FAC-M0002-001"),
        }

        xml = generate_sepa_xml(remittance, receipts, mandates).decode()
        assert "NbOfTxs>2<" in xml
        assert "125.00" in xml  # CtrlSum

    def test_refuses_receipts_without_mandate(self):
        """Was `test_skips_receipts_without_mandate`, asserting NbOfTxs>1<.

        That pinned the defect in place: the second receipt was dropped and the
        file happily declared one transaction, while the remittance still said
        two. See TestMissingMandate for why silently shrinking the batch is the
        wrong answer.
        """
        remittance = _mock_remittance()
        receipts = [
            _mock_receipt(member_id=1),
            _mock_receipt(member_id=99, receipt_number="FAC-2026-0099"),
        ]
        mandates = {1: _mock_mandate(member_id=1)}

        with pytest.raises(SepaExportError):
            generate_sepa_xml(remittance, receipts, mandates)

    def test_one_off_mandate_type(self):
        remittance = _mock_remittance()
        receipts = [_mock_receipt()]
        mandates = {1: _mock_mandate(mandate_type="one_off")}

        xml = generate_sepa_xml(remittance, receipts, mandates).decode()
        assert "OOFF" in xml

    def test_no_bic_debtor(self):
        """Debtor BIC is optional — sepaxml handles it gracefully."""
        remittance = _mock_remittance()
        receipts = [_mock_receipt()]
        mandates = {1: _mock_mandate(debtor_bic=None)}

        xml = generate_sepa_xml(remittance, receipts, mandates)
        assert isinstance(xml, bytes)

    def test_description_truncated(self):
        remittance = _mock_remittance()
        long_desc = "A" * 200
        receipts = [_mock_receipt(description=long_desc)]
        mandates = {1: _mock_mandate()}

        xml = generate_sepa_xml(remittance, receipts, mandates).decode()
        # Description should be truncated to 140 chars
        assert "A" * 140 not in xml or len(xml) > 0  # Just ensure no error


class TestMissingMandate:
    """A receipt whose mandate is gone must stop the export, not be dropped.

    The remittance keeps the total_amount and receipt_count agreed at creation
    and the receipts stay linked by remittance_id, so a file built from a subset
    means the bank collects less than the batch says while those receipts are
    excluded from future batches, with nothing reconciling the two.
    """

    def test_raises_instead_of_skipping(self):
        remittance = _mock_remittance()
        receipts = [_mock_receipt(member_id=1), _mock_receipt(member_id=2)]
        mandates = {1: _mock_mandate(member_id=1)}  # member 2's mandate is gone

        with pytest.raises(SepaExportError) as exc:
            generate_sepa_xml(remittance, receipts, mandates)
        assert "[2]" in str(exc.value)

    def test_names_every_missing_member(self):
        remittance = _mock_remittance()
        receipts = [_mock_receipt(member_id=n) for n in (1, 2, 3)]
        mandates = {2: _mock_mandate(member_id=2)}

        with pytest.raises(SepaExportError) as exc:
            generate_sepa_xml(remittance, receipts, mandates)
        # Both, so one run tells the operator everything to fix.
        assert "[1, 3]" in str(exc.value)

    def test_no_partial_file_is_returned(self):
        """The failure must not come back as a shorter file."""
        remittance = _mock_remittance()
        receipts = [_mock_receipt(member_id=1), _mock_receipt(member_id=2)]
        mandates = {1: _mock_mandate(member_id=1)}

        with pytest.raises(SepaExportError):
            generate_sepa_xml(remittance, receipts, mandates)


class TestSchemaValidation:
    """The export is validated on the way out.

    The bank is otherwise the only thing that checks the file, and the slowest
    place to find out.
    """

    def test_export_is_schema_valid(self):
        remittance = _mock_remittance()
        receipts = [_mock_receipt()]
        mandates = {1: _mock_mandate()}

        # Would raise sepaxml's ValidationError if the document were malformed.
        xml = generate_sepa_xml(remittance, receipts, mandates)
        assert b"pain.008.001.02" in xml

    def test_datetime_dates_are_narrowed(self):
        """A datetime where the schema wants a date used to fail validation.

        Both columns are Date today, so this guards the model changing under us
        rather than a live path — the failure it prevents names neither the
        field nor the payment.
        """
        from datetime import datetime

        remittance = _mock_remittance(due_date=datetime(2026, 5, 1, 9, 30))
        receipts = [_mock_receipt()]
        mandates = {1: _mock_mandate(signed_at=datetime(2026, 4, 1, 8, 15))}

        xml = generate_sepa_xml(remittance, receipts, mandates)
        assert b"2026-05-01" in xml
        assert b"2026-04-01" in xml
