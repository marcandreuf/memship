"""The receipt PDF writes amounts the way its reader does (#607)."""

import pytest

from app.domains.billing.pdf import DOCUMENT_LABELS, _env


def _render(locale: str) -> str:
    return _env.get_template(f"receipt_{locale}.html").render(
        locale=locale,
        document_labels=DOCUMENT_LABELS[locale],
        org={"name": "Club", "currency": "EUR"},
        recipient={"name": "Ana"},
        receipt={
            "receipt_number": "FAC-2026-0001",
            "description": "Cuota",
            "base_amount": "100.00",
            "net_amount": "90.00",
            "vat_rate": "21",
            "vat_amount": "18.90",
            "total_amount": "108.90",
            "discount_amount": "10.00",
        },
    )


@pytest.mark.parametrize(
    "locale,total,discount",
    [
        ("es", "108,90\xa0€", "-10,00\xa0€"),
        ("ca", "108,90\xa0€", "-10,00\xa0€"),
        ("en", "€108.90", "-€10.00"),
    ],
)
def test_amounts_follow_the_receipt_locale(locale, total, discount):
    html = _render(locale)

    assert total in html
    assert discount in html
    assert "EUR" not in html
