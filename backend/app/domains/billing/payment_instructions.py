"""How a member is told to pay a receipt, shared by every email that asks.

The payment reminder used to be the only email carrying a way to pay, so a club
collecting by card sent its members a dunning notice as their first actionable
prompt (#436). The receipt-delivery email now asks too, from the same rules.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.domains.billing.models import PaymentProvider, Receipt, SepaMandate
from app.domains.organizations.models import OrganizationSettings

# Receipt statuses that still owe money.
PAYABLE_STATUSES = ("emitted", "overdue")


@dataclass(frozen=True)
class PaymentInstructions:
    pay_now_url: str | None = None
    bank_details: str | None = None
    direct_debit: bool = False


def has_active_online_provider(db: Session) -> bool:
    return (
        db.query(PaymentProvider)
        .filter(PaymentProvider.status.in_(["active", "test"]))
        .first()
        is not None
    )


def how_to_pay(db: Session, org: OrganizationSettings | None, locale: str) -> PaymentInstructions:
    """A pay button when an online provider is live, else the bank details."""
    if has_active_online_provider(db):
        # The member's own page, not /receipts — that one is the admin list,
        # gated on `billing.read`, so the portal layout bounced the recipient of
        # every reminder we sent straight to /dashboard. See
        # frontend/lib/route-permissions.ts: /my-receipts wants
        # `self.billing.read`, which is what a member actually holds.
        return PaymentInstructions(pay_now_url=f"{settings.FRONTEND_URL}/{locale}/my-receipts")
    if org and org.bank_iban:
        return PaymentInstructions(
            bank_details=" — ".join(filter(None, [org.bank_name, org.bank_iban]))
        )
    return PaymentInstructions()


def owes_money(receipt: Receipt) -> bool:
    # A credit note moves money back to the member, and a zero total collects
    # nothing — neither is something to pay.
    return (
        receipt.status in PAYABLE_STATUSES
        and receipt.document_type == "invoice"
        and receipt.total_amount > 0
    )


def collected_by_direct_debit(db: Session, receipt: Receipt) -> bool:
    """Whether a SEPA remittance will collect this receipt without the member.

    The mandate and batchable half of ``sepa_eligible_receipts_query``; the rest
    of its conditions are ``owes_money``. Offering such a member a pay button
    invites them to pay once by card and again when the bank debits them.
    """
    if not receipt.is_batchable:
        return False
    return (
        db.query(SepaMandate.id)
        .filter(
            SepaMandate.party_id == receipt.party_id,
            SepaMandate.status == "active",
            SepaMandate.is_active.is_(True),
        )
        .first()
        is not None
    )


def delivery_instructions(
    db: Session, receipt: Receipt, org: OrganizationSettings | None, locale: str
) -> PaymentInstructions:
    """What the receipt-delivery email tells the member about paying."""
    if not owes_money(receipt):
        return PaymentInstructions()
    if collected_by_direct_debit(db, receipt):
        return PaymentInstructions(direct_debit=True)
    return how_to_pay(db, org, locale)
