"""SEPA XML generation using the sepaxml library (pain.008.001.02)."""

from datetime import date, datetime
from decimal import Decimal

from sepaxml import SepaDD

from app.domains.billing.models import Receipt, Remittance, SepaMandate


class SepaExportError(Exception):
    """The batch cannot be turned into a valid pain.008 file.

    Raised instead of writing a file that does not match the remittance it came
    from. A remittance carries the ``total_amount`` and ``receipt_count`` agreed
    when it was created, and its receipts stay linked by ``remittance_id``, so a
    file quietly built from a subset means the bank collects less than the batch
    says while those receipts are excluded from future batches. Nothing
    reconciles the two afterwards.

    ``party_ids`` carries the parties the caller must name in its own error.
    The message here is a fallback for a caller that has no session to resolve
    them with.
    """

    def __init__(self, message: str, party_ids: list[int] | None = None) -> None:
        super().__init__(message)
        self.party_ids = party_ids or []


def _as_date(value: date | datetime) -> date:
    """Narrow a datetime to a date.

    sepaxml's schema validation rejects a ``datetime`` where pain.008 wants a
    date, and the failure message names neither the field nor the payment. Both
    columns feeding this module are ``Date`` today, so this is a guard against a
    model change reintroducing an error that is hard to read.
    """
    return value.date() if isinstance(value, datetime) else value


def generate_sepa_xml(
    remittance: Remittance,
    receipts: list[Receipt],
    mandates: dict[int, SepaMandate],
) -> bytes:
    """Generate a SEPA Direct Debit XML file (pain.008.001.02).

    Args:
        remittance: The remittance batch.
        receipts: Receipts included in this batch.
        mandates: Dict mapping party_id -> active SepaMandate.

    Returns:
        XML content as bytes.

    Raises:
        SepaExportError: a receipt has no mandate in ``mandates``.
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

    # Checked up front so the message names every affected member, rather than
    # failing on the first one and hiding the rest behind a second run.
    missing = sorted({r.party_id for r in receipts if r.party_id not in mandates})
    if missing:
        # The ids travel on the exception so the caller, which has the session,
        # can name these members the way the admin sees them. A cancelled
        # mandate cannot be reinstated and a receipt cannot be taken out of a
        # batch on its own, so the only way forward is a fresh mandate and a
        # fresh remittance — which is what the message must say.
        raise SepaExportError(
            "Cannot generate the SEPA file: no active mandate for member(s) "
            f"{missing}. The mandate was most likely cancelled after this "
            "remittance was created. Create a new mandate for those members, "
            "then cancel this remittance and create it again.",
            party_ids=missing,
        )

    for receipt in receipts:
        mandate = mandates[receipt.party_id]

        # sepaxml expects amount in cents (integer)
        amount_cents = int(Decimal(str(receipt.total_amount)) * 100)

        payment = {
            "name": mandate.debtor_name,
            "IBAN": mandate.debtor_iban,
            "amount": amount_cents,
            "type": "RCUR" if mandate.mandate_type == "recurrent" else "OOFF",
            "collection_date": _as_date(remittance.due_date),
            "mandate_id": mandate.mandate_reference,
            "mandate_date": _as_date(mandate.signed_at),
            "description": f"{receipt.receipt_number} - {receipt.description}"[:140],
        }
        if mandate.debtor_bic:
            payment["BIC"] = mandate.debtor_bic

        dd.add_payment(payment)

    # Validated on the way out. The file goes to a bank, which is the only other
    # thing that checks it and the slowest place to find out. Validation used to
    # be off because sepaxml rejects a datetime where the schema wants a date;
    # `_as_date` removes that cause, so the check can stay on.
    return dd.export(validate=True)
