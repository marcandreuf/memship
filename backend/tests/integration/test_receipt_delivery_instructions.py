"""What the receipt-delivery email tells a member about paying (#436)."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.domains.billing.models import PaymentProvider, Receipt, SepaMandate
from app.domains.billing.payment_instructions import delivery_instructions
from app.domains.members.models import Member, MembershipType
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Person
from app.tasks.email_tasks import send_receipt_email_task

IBAN = "ES9121000418450200051332"


@pytest.fixture
def org(db):
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    if not org:
        org = OrganizationSettings(
            id=1,
            name="Test Organization",
            locale="es",
            timezone="Europe/Madrid",
            currency="EUR",
            date_format="DD/MM/YYYY",
            invoice_prefix="FAC",
            invoice_next_number=1,
            invoice_annual_reset=True,
            default_vat_rate=21.00,
        )
        db.add(org)
    org.bank_name = "Caixa Test"
    org.bank_iban = IBAN
    org.creditor_id = org.creditor_id or "ES12000B12345678"
    db.flush()
    return org


def _member(db, suffix):
    person = Person(
        first_name="María", last_name="García", email=f"rd-{suffix}@examplee6e3b1.com"
    )
    db.add(person)
    db.flush()
    mtype = MembershipType(name=f"RD {suffix}", slug=f"rd-{suffix}", base_price=50.00)
    db.add(mtype)
    db.flush()
    member = Member(
        party_id=person.party_id,
        membership_type_id=mtype.id,
        member_number=f"RD-{suffix}",
        status="active",
    )
    db.add(member)
    db.flush()
    return member


def _receipt(db, member, suffix, status="emitted", total="50.00", batchable=True):
    receipt = Receipt(
        receipt_number=f"RD-{suffix}",
        party_id=member.party_id,
        origin="membership",
        description="Membership fee",
        base_amount=Decimal(total),
        vat_rate=Decimal("0.00"),
        vat_amount=Decimal("0.00"),
        total_amount=Decimal(total),
        status=status,
        emission_date=date(2026, 6, 1),
        due_date=date(2026, 6, 8),
        is_batchable=batchable,
    )
    db.add(receipt)
    db.flush()
    return receipt


def _mandate(db, member, org, suffix):
    db.add(
        SepaMandate(
            party_id=member.party_id,
            mandate_reference=f"FAC-RD{suffix}-001",
            creditor_id=org.creditor_id,
            debtor_name="María García",
            debtor_iban="ES7921000813610123456789",
            debtor_bic="BBVAESMMXXX",
            mandate_type="recurrent",
            signature_method="paper",
            status="active",
            signed_at=date(2026, 4, 1),
        )
    )
    db.flush()


def _online_provider(db):
    db.add(PaymentProvider(provider_type="stripe", display_name="Stripe", status="active"))
    db.flush()


class TestDeliveryInstructions:
    def test_pay_button_to_the_member_page_when_a_provider_is_live(self, db, org):
        _online_provider(db)
        receipt = _receipt(db, _member(db, "p1"), "p1")

        got = delivery_instructions(db, receipt, org, "ca")

        assert got.pay_now_url.endswith("/ca/my-receipts")
        assert got.bank_details is None
        assert not got.direct_debit

    def test_bank_details_when_there_is_only_an_iban(self, db, org):
        receipt = _receipt(db, _member(db, "b1"), "b1")

        got = delivery_instructions(db, receipt, org, "es")

        assert got.pay_now_url is None
        assert IBAN in got.bank_details

    def test_a_mandated_member_is_told_it_is_debited(self, db, org):
        _online_provider(db)
        member = _member(db, "d1")
        _mandate(db, member, org, "d1")
        receipt = _receipt(db, member, "d1")

        got = delivery_instructions(db, receipt, org, "es")

        assert got.direct_debit
        assert got.pay_now_url is None
        assert got.bank_details is None

    def test_a_receipt_kept_out_of_remittances_is_payable_despite_a_mandate(self, db, org):
        _online_provider(db)
        member = _member(db, "d2")
        _mandate(db, member, org, "d2")
        receipt = _receipt(db, member, "d2", batchable=False)

        got = delivery_instructions(db, receipt, org, "es")

        assert not got.direct_debit
        assert got.pay_now_url is not None

    @pytest.mark.parametrize("status", ["paid", "cancelled", "pending"])
    def test_a_receipt_that_does_not_owe_offers_nothing(self, db, org, status):
        _online_provider(db)
        receipt = _receipt(db, _member(db, f"s-{status}"), f"s-{status}", status=status)

        got = delivery_instructions(db, receipt, org, "es")

        assert (got.pay_now_url, got.bank_details, got.direct_debit) == (None, None, False)

    def test_a_zero_receipt_offers_nothing(self, db, org):
        _online_provider(db)
        receipt = _receipt(db, _member(db, "z1"), "z1", total="0.00")

        got = delivery_instructions(db, receipt, org, "es")

        assert (got.pay_now_url, got.bank_details, got.direct_debit) == (None, None, False)


class TestReceiptEmailTask:
    def test_the_task_passes_the_instructions_to_the_mailer(self, db, org):
        _online_provider(db)
        receipt = _receipt(db, _member(db, "t1"), "t1")

        with (
            patch("app.db.session.SessionLocal", return_value=db),
            patch.object(db, "close"),
            patch("app.domains.billing.pdf.generate_receipt_pdf", return_value=b"%PDF"),
            patch("app.tasks.email_tasks.send_receipt_delivery_email", return_value=True) as send,
        ):
            assert send_receipt_email_task.run(receipt.id) is True

        kwargs = send.call_args.kwargs
        assert kwargs["pay_now_url"].endswith("/es/my-receipts")
        assert kwargs["bank_details"] is None
        assert kwargs["direct_debit"] is False
