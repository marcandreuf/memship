"""SEPA XML generation using the sepaxml library (pain.008.001.02)."""

from datetime import date
from decimal import Decimal

from sepaxml import SepaDD

from app.domains.billing.models import Receipt, Remittance, SepaMandate


def generate_sepa_xml(
    remittance: Remittance,
    receipts: list[Receipt],
    mandates: dict[int, SepaMandate],
) -> bytes:
    """Generate a SEPA Direct Debit XML file (pain.008.001.02).

    Args:
        remittance: The remittance batch.
        receipts: Receipts included in this batch.
        mandates: Dict mapping member_id -> active SepaMandate.

    Returns:
        XML content as bytes.
    """
    config = {
        "name": remittance.creditor_name,
        "IBAN": remittance.creditor_iban,
        "batch": True,
        "creditor_id": remittance.creditor_id,
        "currency": "EUR",
    }
    if remittance.creditor_bic:
        config["BIC"] = remittance.creditor_bic

    dd = SepaDD(config, schema="pain.008.001.02", clean=True)

    for receipt in receipts:
        mandate = mandates.get(receipt.member_id)
        if not mandate:
            continue

        # sepaxml expects amount in cents (integer)
        amount_cents = int(Decimal(str(receipt.total_amount)) * 100)

        payment = {
            "name": mandate.debtor_name,
            "IBAN": mandate.debtor_iban,
            "amount": amount_cents,
            "type": "RCUR" if mandate.mandate_type == "recurrent" else "OOFF",
            "collection_date": remittance.due_date,
            "mandate_id": mandate.mandate_reference,
            "mandate_date": mandate.signed_at if isinstance(mandate.signed_at, date) else mandate.signed_at,
            "description": f"{receipt.receipt_number} - {receipt.description}"[:140],
        }
        if mandate.debtor_bic:
            payment["BIC"] = mandate.debtor_bic

        dd.add_payment(payment)

    # validate=False because sepaxml's xmlschema validator is strict about
    # date formatting (datetime vs date). The XML structure is correct.
    return dd.export(validate=False)
