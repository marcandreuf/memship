"""Unit tests for booking email rendering — templates exist in every locale."""

import pytest

from app.core.email import render_template

KINDS = [
    "booking_confirmation",
    "booking_waitlisted",
    "booking_promoted",
    "booking_cancelled",
]
CONTEXT = {
    "member_name": "Alex",
    "space_name": "Court 1",
    "booking_date": "24/07/2026",
    "booking_time": "10:00–11:00",
    "cancellation_deadline_hours": 24,
    "position": 2,
}


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("locale", ["es", "ca", "en"])
def test_booking_template_renders(kind, locale):
    html = render_template(kind, locale, CONTEXT)
    assert "Court 1" in html
    assert html.strip()


PAYMENT = {
    "amount": "12.10",
    "currency": "EUR",
    "deadline": "24/07/2026 09:00",
    "pay_now_url": "https://club.example/es/my-receipts",
    "bank_details": "Banco — ES9121000418450200051332",
    "cash": True,
    "reference": "FAC-2026-0001 – Alex Pérez",
}


@pytest.mark.parametrize("locale", ["es", "ca", "en"])
def test_a_booking_held_until_paid_says_how_much_by_when_and_how(locale):
    html = render_template(
        "booking_pending_payment", locale, {**CONTEXT, **PAYMENT}
    )
    assert "Court 1" in html
    assert "24/07/2026 09:00" in html
    assert "my-receipts" in html
    assert "ES9121000418450200051332" in html
    assert "FAC-2026-0001" in html


def test_cash_alone_is_not_offered_as_an_alternative():
    html = render_template(
        "booking_pending_payment",
        "es",
        {**CONTEXT, **PAYMENT, "pay_now_url": None, "bank_details": None},
    )
    assert "Puedes pagar en efectivo en el club." in html
    assert "También" not in html
