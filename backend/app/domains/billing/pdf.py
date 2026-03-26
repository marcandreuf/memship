"""Receipt PDF generation using WeasyPrint + Jinja2."""

from io import BytesIO
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session

from app.domains.billing.models import Receipt
from app.domains.members.models import Member
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Address, Person

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
        .filter(Address.entity_type == "organization", Address.entity_id == 1, Address.is_primary.is_(True))
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


def _get_member_address(db: Session, person_id: int) -> str | None:
    """Get a member's primary address as a single string."""
    addr = (
        db.query(Address)
        .filter(Address.entity_type == "person", Address.entity_id == person_id, Address.is_primary.is_(True))
        .first()
    )
    if not addr:
        return None
    parts = [addr.address_line1]
    if addr.address_line2:
        parts.append(addr.address_line2)
    parts.append(f"{addr.postal_code} {addr.city}" if addr.postal_code else addr.city)
    return ", ".join(parts)


def generate_receipt_pdf(db: Session, receipt: Receipt) -> bytes:
    """Generate a PDF for a receipt.

    Returns the PDF as bytes.
    """
    # Lazy import to avoid ImportError when WeasyPrint system deps are missing (e.g., in tests)
    from weasyprint import HTML

    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()
    member = db.query(Member).filter(Member.id == receipt.member_id).first()
    person = db.query(Person).filter(Person.id == member.person_id).first() if member else None

    locale = org.locale or "es"
    if locale not in ("es", "ca", "en"):
        locale = "es"

    template_name = f"receipt_{locale}.html"
    template = _env.get_template(template_name)

    org_address = _get_org_address(db)
    member_address = _get_member_address(db, person.id) if person else None

    context = {
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
            "description": receipt.description,
            "base_amount": f"{receipt.base_amount:.2f}",
            "vat_rate": f"{receipt.vat_rate:.0f}" if receipt.vat_rate == int(receipt.vat_rate) else f"{receipt.vat_rate:.2f}",
            "vat_amount": f"{receipt.vat_amount:.2f}",
            "total_amount": f"{receipt.total_amount:.2f}",
            "discount_amount": f"{receipt.discount_amount:.2f}" if receipt.discount_amount else None,
            "discount_type": receipt.discount_type,
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
            "name": f"{person.first_name} {person.last_name}" if person else "—",
            "email": person.email if person else None,
            "tax_id": person.national_id if person else None,
            "address": member_address,
            "member_number": member.member_number if member else "—",
        },
        "status_label": STATUS_LABELS.get(locale, STATUS_LABELS["es"]).get(receipt.status, receipt.status),
        "payment_method_label": PAYMENT_METHOD_LABELS.get(locale, PAYMENT_METHOD_LABELS["es"]).get(receipt.payment_method, receipt.payment_method) if receipt.payment_method else None,
    }

    html_content = template.render(**context)
    pdf_bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes
