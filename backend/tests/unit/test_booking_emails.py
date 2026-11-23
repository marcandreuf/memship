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


@pytest.mark.parametrize("locale", ["es", "ca", "en"])
def test_a_promotion_held_until_paid_says_how_to_pay(locale):
    html = render_template("booking_promoted", locale, {**CONTEXT, **PAYMENT})
    assert "24/07/2026 09:00" in html
    assert "my-receipts" in html


@pytest.mark.parametrize("locale", ["es", "ca", "en"])
def test_a_seat_freed_late_is_offered_with_its_price_deadline_and_link(locale):
    html = render_template(
        "booking_seat_available",
        locale,
        {
            **CONTEXT,
            "amount": "12.10",
            "currency": "EUR",
            "deadline": "24/07/2026 09:00",
            "book_url": "https://club.example/es/book?space=3&date=2026-07-24",
        },
    )
    assert "Court 1" in html
    assert "24/07/2026 09:00" in html
    assert "book?space=3" in html


@pytest.mark.parametrize("locale", ["es", "ca", "en"])
def test_the_deadline_reminder_says_how_to_pay_before_it(locale):
    html = render_template(
        "booking_deadline_reminder", locale, {**CONTEXT, **PAYMENT}
    )
    assert "Court 1" in html
    assert "24/07/2026 09:00" in html
    assert "my-receipts" in html


@pytest.mark.parametrize("locale", ["es", "ca", "en"])
def test_a_booking_released_unpaid_names_the_slot(locale):
    html = render_template("booking_cancelled_unpaid", locale, CONTEXT)
    assert "Court 1" in html
    assert "24/07/2026" in html


@pytest.mark.parametrize(
    "locale,heading",
    [
        ("es", "Ahora tienes menos tiempo para pagar"),
        ("ca", "Ara tens menys temps per pagar"),
        ("en", "You now have less time to pay"),
    ],
)
def test_a_deadline_brought_forward_says_so(locale, heading):
    html = render_template(
        "booking_pending_payment",
        locale,
        {**CONTEXT, **PAYMENT, "deadline_changed": True},
    )
    assert heading in html
