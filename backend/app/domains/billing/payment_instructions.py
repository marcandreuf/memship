"""How a member is told to pay a receipt, shared by every email that asks.

The payment reminder used to be the only email carrying a way to pay, so a club
collecting by card sent its members a dunning notice as their first actionable
prompt (#436). The receipt-delivery email now asks too, from the same rules.

A receipt for a pay-to-confirm seat is narrower: its activity names the methods
it accepts, and every email and screen offers those and nothing else (#591). A
cash-only activity whose receipt email carried a card button invited payments
the organiser never agreed to take.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.domains.activities.models import PAYMENT_FLOW_PAY_TO_CONFIRM
from app.domains.billing.models import PaymentProvider, Receipt, SepaMandate
from app.domains.billing.provider_config import member_payment_methods
from app.domains.organizations.models import OrganizationSettings

# Receipt statuses that still owe money.
PAYABLE_STATUSES = ("emitted", "overdue")

# The statuses that put a provider in front of members: `/active-methods`
# selects on these, and the member's pay buttons are built from that list alone.
MEMBER_FACING_STATUSES = ("active", "test")

# What a member can pay with online. SEPA direct debit is a provider too, but
# the club collects it; a member cannot press a button to pay by it.
ONLINE_METHODS = frozenset({"card", "bizum"})


@dataclass(frozen=True)
class PaymentInstructions:
    pay_now_url: str | None = None
    bank_details: str | None = None
    cash: bool = False
    direct_debit: bool = False


def online_methods_available(db: Session) -> set[str]:
    """The online methods a member can pay with today.

    Built from ``member_payment_methods``, the rule the member's pay buttons
    already follow, so an email cannot promise a method the portal won't draw:
    card when Stripe or Redsys is live, Bizum only where Redsys has it enabled.
    """
    rows = (
        db.query(PaymentProvider.provider_type, PaymentProvider.config)
        .filter(PaymentProvider.status.in_(MEMBER_FACING_STATUSES))
        .all()
    )
    available: set[str] = set()
    for provider_type, config in rows:
        available.update(member_payment_methods(provider_type, config))
    return available & ONLINE_METHODS


def receipt_allowed_methods(receipt: Receipt) -> list[str] | None:
    """The methods a receipt may be paid by, or None when anything goes.

    Only a pay-to-confirm seat is restricted, to what its activity accepts.
    """
    registration = receipt.registration
    activity = registration.activity if registration else None
    if activity is None or activity.payment_flow != PAYMENT_FLOW_PAY_TO_CONFIRM:
        return None
    return list(activity.payment_methods or [])


def bank_details_of(org: OrganizationSettings | None) -> str | None:
    if org and org.bank_iban:
        return " — ".join(filter(None, [org.bank_name, org.bank_iban]))
    return None


def _pay_now_url(locale: str) -> str:
    # The member's own page, not /receipts — that one is the admin list,
    # gated on `billing.read`, so the portal layout bounced the recipient of
    # every reminder we sent straight to /dashboard. See
    # frontend/lib/route-permissions.ts: /my-receipts wants
    # `self.billing.read`, which is what a member actually holds.
    return f"{settings.FRONTEND_URL}/{locale}/my-receipts"


def how_to_pay(
    db: Session,
    org: OrganizationSettings | None,
    locale: str,
    allowed: Iterable[str] | None = None,
) -> PaymentInstructions:
    """How to pay, from the methods ``allowed`` (None: any the club offers).

    Unrestricted, it is a pay button when an online method is live, else the
    bank details. Restricted, each accepted method the club can take is listed.
    """
    online = online_methods_available(db)
    if allowed is None:
        if online:
            return PaymentInstructions(pay_now_url=_pay_now_url(locale))
        return PaymentInstructions(bank_details=bank_details_of(org))
    accepted = set(allowed)
    return PaymentInstructions(
        pay_now_url=_pay_now_url(locale) if online & accepted else None,
        bank_details=bank_details_of(org) if "transfer" in accepted else None,
        cash="cash" in accepted,
    )


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


def receipt_instructions(
    db: Session, receipt: Receipt, org: OrganizationSettings | None, locale: str
) -> PaymentInstructions:
    """How to pay this receipt, honouring its activity's accepted methods."""
    return how_to_pay(db, org, locale, receipt_allowed_methods(receipt))


def delivery_instructions(
    db: Session, receipt: Receipt, org: OrganizationSettings | None, locale: str
) -> PaymentInstructions:
    """What the receipt-delivery email tells the member about paying."""
    if not owes_money(receipt):
        return PaymentInstructions()
    if collected_by_direct_debit(db, receipt):
        return PaymentInstructions(direct_debit=True)
    return receipt_instructions(db, receipt, org, locale)
