"""Mandate PDF generation using WeasyPrint + Jinja2."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session

from app.domains.billing.models import SepaMandate
from app.domains.organizations.models import OrganizationSettings
from app.domains.persons.models import Address

TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "pdf"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=True,
)


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


def generate_mandate_pdf(db: Session, mandate: SepaMandate) -> bytes:
    """Generate a paper mandate PDF for signing.

    Returns the PDF as bytes.
    """
    # Lazy import to avoid ImportError when WeasyPrint system deps are missing (e.g., in tests)
    from weasyprint import HTML

    org = db.query(OrganizationSettings).filter(OrganizationSettings.id == 1).first()

    locale = org.locale or "es"
    if locale not in ("es", "ca", "en"):
        locale = "es"

    template_name = f"mandate_{locale}.html"
    template = _env.get_template(template_name)

    org_address = _get_org_address(db)

    context = {
        "creditor": {
            "name": org.name,
            "legal_name": org.legal_name,
            "tax_id": org.tax_id,
            "address": org_address,
            "creditor_id": mandate.creditor_id,
            "iban": org.bank_iban,
            "bic": org.bank_bic,
        },
        "debtor": {
            "name": mandate.debtor_name,
            "iban": mandate.debtor_iban,
            "bic": mandate.debtor_bic,
        },
        "mandate": {
            "reference": mandate.mandate_reference,
            "type": mandate.mandate_type,
        },
    }

    html_content = template.render(**context)
    pdf_bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes
