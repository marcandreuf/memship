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
