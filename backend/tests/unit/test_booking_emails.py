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
    "cancellation_deadline_minutes": 1440,
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


@pytest.mark.parametrize(
    "locale,heading",
    [("es", "Hay una plaza para ti"), ("ca", "Hi ha una plaça per a tu"), ("en", "There is a place for you")],
)
def test_a_promotion_held_until_paid_says_so_and_how_to_pay(locale, heading):
    html = render_template(
        "booking_pending_payment", locale, {**CONTEXT, **PAYMENT, "promoted": True}
    )
    assert heading in html
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


@pytest.mark.parametrize(
    "locale, refundable, kept",
    [
        ("en", "cancel for a refund up to 24 hours", "payment will not be returned"),
        ("es", "cancelar con devolución hasta 24 horas", "pago no se devolverá"),
        ("ca", "cancel·lar amb devolució fins a 24 hores", "pagament no es retornarà"),
    ],
)
def test_a_paid_booking_that_may_be_cancelled_late_says_the_payment_is_kept(
    locale, refundable, kept
):
    html = render_template(
        "booking_confirmation",
        locale,
        {**CONTEXT, "late_cancellation_keeps_payment": True},
    )
    assert refundable in html
    assert kept in html


@pytest.mark.parametrize(
    "locale, sentence",
    [
        ("en", "You can cancel up to 24 hours before the start."),
        ("es", "Puedes cancelar hasta 24 horas antes del inicio."),
        ("ca", "Pots cancel·lar fins a 24 hores abans de l'inici."),
    ],
)
def test_otherwise_the_confirmation_keeps_its_plain_deadline_sentence(locale, sentence):
    html = render_template("booking_confirmation", locale, CONTEXT)
    assert sentence in html
    assert "refund" not in html.lower() and "devolució" not in html


def test_a_deadline_in_minutes_is_not_rounded_into_hours():
    html = render_template(
        "booking_confirmation", "en", {**CONTEXT, "cancellation_deadline_minutes": 30}
    )
    assert "up to 30 minutes before" in html
