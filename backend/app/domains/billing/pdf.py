"""Receipt PDF generation using WeasyPrint + Jinja2."""

from decimal import Decimal
from io import BytesIO
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session

from app.domains.billing.models import Receipt
from app.domains.billing.service import resolve_discount
from app.domains.members.models import Member
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Address, Party, Person

TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "pdf"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=True,
)

STATUS_LABELS = {
    "es": {
        "new": "Nuevo",
        "pending": "Pendiente",
        "emitted": "Emitido",
        "paid": "Cobrado",
        "returned": "Devuelto",
        "cancelled": "Anulado",
        "overdue": "Vencido",
    },
    "ca": {
        "new": "Nou",
        "pending": "Pendent",
        "emitted": "Emès",
        "paid": "Cobrat",
        "returned": "Retornat",
        "cancelled": "Anul·lat",
        "overdue": "Vençut",
    },
    "en": {
        "new": "New",
        "pending": "Pending",
        "emitted": "Issued",
        "paid": "Paid",
        "returned": "Returned",
        "cancelled": "Cancelled",
        "overdue": "Overdue",
    },
}

DOCUMENT_LABELS = {
    "es": {
        "invoice": "RECIBO",
        "credit_note": "FACTURA RECTIFICATIVA",
        "rectifies": "Rectifica el documento",
    },
    "ca": {
        "invoice": "REBUT",
        "credit_note": "FACTURA RECTIFICATIVA",
        "rectifies": "Rectifica el document",
    },
    "en": {
        "invoice": "RECEIPT",
        "credit_note": "CREDIT NOTE",
        "rectifies": "Rectifies document",
    },
}

PAYMENT_METHOD_LABELS = {
    "es": {
        "cash": "Efectivo",
        "bank_transfer": "Transferencia bancaria",
        "card": "Tarjeta",
        "direct_debit": "Domiciliación bancaria",
    },
    "ca": {
        "cash": "Efectiu",
        "bank_transfer": "Transferència bancària",
        "card": "Targeta",
        "direct_debit": "Domiciliació bancària",
    },
    "en": {
        "cash": "Cash",
        "bank_transfer": "Bank transfer",
        "card": "Card",
        "direct_debit": "Direct debit",
    },
}


def _get_org_address(db: Session) -> str | None:
    """Get the organization address as a single string."""
    addr = (
        db.query(Address)
        .join(OrganizationSettings, OrganizationSettings.party_id == Address.party_id)
        .filter(Address.is_primary.is_(True))
        .first()
    )
    if not addr:
        return None
    parts = [addr.address_line1]
    if addr.address_line2:
        parts.append(addr.address_line2)
    parts.append(f"{addr.postal_code} {addr.city}" if addr.postal_code else addr.city)
    if addr.state_province and addr.state_province != addr.city:
        parts[-1] += f", {addr.state_province}"
    if addr.country:
        parts[-1] += f" ({addr.country})"
    return ", ".join(parts)


def _get_member_address(db: Session, party_id: int) -> str | None:
    """Get a member's primary address as a single string."""
    addr = (
        db.query(Address)
        .filter(Address.party_id == party_id, Address.is_primary.is_(True))
        .first()
    )
    if not addr:
        return None
    parts = [addr.address_line1]
    if addr.address_line2:
        parts.append(addr.address_line2)
    parts.append(f"{addr.postal_code} {addr.city}" if addr.postal_code else addr.city)
    return ", ".join(parts)


def build_receipt_context(db: Session, receipt: Receipt) -> dict:
    """Assemble everything the receipt template renders.

    Split out of :func:`generate_receipt_pdf` so the recipient can be asserted
    without WeasyPrint, whose system deps are deliberately absent in tests --
    the same reason the import below is lazy.
    """
    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    member = (
        db.query(Member)
        .filter(Member.party_id == receipt.party_id)
        .order_by(Member.is_active.desc(), Member.id.desc())
        .first()
    )
    person = db.query(Person).filter(Person.party_id == member.party_id).first() if member else None
    # The recipient is the receipt's party. Loading only the person left a
    # donation receipt to a company with no name, no tax id and no address,
    # which a Spanish factura cannot be issued without.
    party = db.query(Party).filter(Party.id == receipt.party_id).first()

    locale = org.locale or "es"
    if locale not in ("es", "ca", "en"):
        locale = "es"

    org_address = _get_org_address(db)
    recipient_address = _get_member_address(db, receipt.party_id)
    discount = resolve_discount(
        Decimal(str(receipt.base_amount)), receipt.discount_amount, receipt.discount_type
    )

    context = {
        "locale": locale,
        "org": {
            "name": org.name,
            "legal_name": org.legal_name,
            "tax_id": org.tax_id,
            "email": org.email,
            "phone": org.phone,
            "website": org.website,
            "address": org_address,
            "currency": org.currency or "EUR",
            "bank_name": org.bank_name,
            "bank_iban": org.bank_iban,
            "bank_bic": org.bank_bic,
        },
        "receipt": {
            "receipt_number": receipt.receipt_number,
            "document_type": receipt.document_type,
            "rectifies_receipt_number": (
                receipt.rectifies.receipt_number if receipt.rectifies else None
            ),
            "description": receipt.description,
            "base_amount": f"{receipt.base_amount:.2f}",
            "net_amount": f"{Decimal(str(receipt.base_amount)) - discount:.2f}",
            "vat_rate": f"{receipt.vat_rate:.0f}" if receipt.vat_rate == int(receipt.vat_rate) else f"{receipt.vat_rate:.2f}",
            "vat_amount": f"{receipt.vat_amount:.2f}",
            "total_amount": f"{receipt.total_amount:.2f}",
            # The money taken off, and the percentage it came from when it did.
            "discount_amount": f"{discount:.2f}" if discount else None,
            "discount_percentage": (
                f"{receipt.discount_amount:g}"
                if discount and receipt.discount_type == "percentage"
                else None
            ),
            "status": receipt.status,
            "emission_date": receipt.emission_date.strftime("%d/%m/%Y") if receipt.emission_date else None,
            "due_date": receipt.due_date.strftime("%d/%m/%Y") if receipt.due_date else None,
            "payment_method": receipt.payment_method,
            "payment_date": receipt.payment_date.strftime("%d/%m/%Y") if receipt.payment_date else None,
            "return_reason": receipt.return_reason,
            "return_date": receipt.return_date.strftime("%d/%m/%Y") if receipt.return_date else None,
            "billing_period_start": receipt.billing_period_start.strftime("%d/%m/%Y") if receipt.billing_period_start else None,
            "billing_period_end": receipt.billing_period_end.strftime("%d/%m/%Y") if receipt.billing_period_end else None,
            "notes": receipt.notes,
        },
        "member": {
            # legal_name first for a non-person recipient: a factura names the
            # registered entity, while display_name is what the screens show
            # and is often a trading name.
            "name": (
                f"{person.first_name} {person.last_name}"
                if person
                else ((party.legal_name or party.display_name) if party else None)
            ),
            "email": person.email if person else (party.email if party else None),
            "tax_id": (
                person.national_id if person else (party.national_id if party else None)
            ),
            "address": recipient_address,
            # A membership fact, so it is absent rather than a dash when the
            # recipient holds no membership. The template omits the line.
            "member_number": member.member_number if member else None,
        },
        "document_labels": DOCUMENT_LABELS.get(locale, DOCUMENT_LABELS["es"]),
        "status_label": STATUS_LABELS.get(locale, STATUS_LABELS["es"]).get(receipt.status, receipt.status),
        "payment_method_label": PAYMENT_METHOD_LABELS.get(locale, PAYMENT_METHOD_LABELS["es"]).get(receipt.payment_method, receipt.payment_method) if receipt.payment_method else None,
    }

    return context


def generate_receipt_pdf(db: Session, receipt: Receipt) -> bytes:
    """Render a receipt as PDF bytes."""
    # Lazy import: WeasyPrint's system deps are missing in the test image.
    from weasyprint import HTML

    context = build_receipt_context(db, receipt)
    template = _env.get_template(f"receipt_{context['locale']}.html")
    return HTML(string=template.render(**context)).write_pdf()
