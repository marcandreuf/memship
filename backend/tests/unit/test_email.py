"""Unit tests for email service."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.email import (
    render_template,
    send_email,
    send_password_reset_email,
    send_registration_cancellation_email,
    send_registration_confirmation_email,
    send_waitlist_promotion_email,
    send_welcome_email,
)
from app.domains.mailing.mailing_config import ResolvedMailing, ResolvedProvider


def _provider(name, values, sources=None):
    return ResolvedProvider(
        name=name,
        values=values,
        sources=sources or {k: "db" for k in values},
        secret_flags={},
    )


def _resolved(active, resend_values=None, gmail_values=None, gmail_sources=None):
    return ResolvedMailing(
        active=active,
        resend=_provider("resend", resend_values or {}),
        gmail=_provider("gmail", gmail_values or {}, gmail_sources),
    )


class TestEmailTransport:
    """Transport selection is now DB-driven via the resolved mailing config."""

    @patch("app.core.email._resolve_transport")
    def test_send_email_no_active_provider(self, mock_resolve):
        mock_resolve.return_value = _resolved(active=None)
        assert send_email("test@example.com", "Test", "<p>body</p>") is False

    @patch("app.core.email._resolve_transport")
    @patch("app.core.email.smtplib.SMTP")
    def test_send_email_gmail_smtp_success(self, mock_smtp_class, mock_resolve):
        mock_resolve.return_value = _resolved(
            active="gmail",
            gmail_values={
                "user": "club@gmail.com",
                "app_password": "app-pw",
                "from_email": "club@gmail.com",
            },
        )
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        result = send_email("test@example.com", "Test Subject", "<p>Hello</p>")

        assert result is True
        # UI-configured Gmail pins Google's SMTP endpoint.
        mock_smtp_class.assert_called_once_with("smtp.gmail.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("club@gmail.com", "app-pw")
        mock_server.sendmail.assert_called_once()

    @patch("app.core.email._resolve_transport")
    @patch("app.core.email.smtplib.SMTP")
    def test_send_email_smtp_failure(self, mock_smtp_class, mock_resolve):
        mock_resolve.return_value = _resolved(
            active="gmail",
            gmail_values={"user": "club@gmail.com", "app_password": "pw"},
        )
        mock_smtp_class.side_effect = ConnectionRefusedError("Connection refused")

        assert send_email("test@example.com", "Test", "<p>body</p>") is False

    @patch("app.core.email._resolve_transport")
    def test_send_email_resend(self, mock_resolve):
        mock_resolve.return_value = _resolved(
            active="resend",
            resend_values={"api_key": "re_key", "from_email": "noreply@club.example"},
        )
        with patch("app.core.email._send_via_resend", return_value=True) as mock_resend:
            result = send_email("test@example.com", "Test", "<p>body</p>")
            assert result is True
            mock_resend.assert_called_once()


class TestTemplateRendering:
    def test_render_template_es(self):
        html = render_template("welcome", "es", {"first_name": "María", "member_number": "M-001"})
        assert "María" in html
        assert "M-001" in html
        assert "Bienvenido" in html

    def test_render_template_ca(self):
        html = render_template("welcome", "ca", {"first_name": "Joan", "member_number": "M-002"})
        assert "Joan" in html
        assert "Benvingut" in html

    def test_render_template_en(self):
        html = render_template("welcome", "en", {"first_name": "John", "member_number": "M-003"})
        assert "John" in html
        assert "Welcome" in html

    def test_render_template_fallback_to_es(self):
        """Unknown locale falls back to ES."""
        html = render_template("welcome", "fr", {"first_name": "Pierre", "member_number": "M-004"})
        assert "Pierre" in html
        assert "Bienvenido" in html

    def test_render_registration_confirmed(self):
        html = render_template("registration_confirmed", "en", {
            "member_name": "Alice",
            "activity_name": "Yoga",
            "activity_date": "15/07/2026",
            "location": "Main Hall",
        })
        assert "Alice" in html
        assert "Yoga" in html
        assert "15/07/2026" in html
        assert "Main Hall" in html

    def test_render_registration_waitlisted(self):
        html = render_template("registration_waitlisted", "es", {
            "member_name": "Carlos",
            "activity_name": "Fútbol",
            "activity_date": None,
            "location": None,
        })
        assert "Carlos" in html
        assert "lista de espera" in html

    def test_render_registration_cancelled(self):
        html = render_template("registration_cancelled", "ca", {
            "member_name": "Joan",
            "activity_name": "Natació",
            "cancelled_by": "Admin",
        })
        assert "Joan" in html
        assert "cancel·lada" in html

    def test_render_waitlist_promoted(self):
        html = render_template("waitlist_promoted", "en", {
            "member_name": "Bob",
            "activity_name": "Chess",
            "activity_date": "01/08/2026",
            "location": "Room A",
        })
        assert "Bob" in html
        assert "confirmed" in html.lower()

    def test_render_password_reset(self):
        html = render_template("password_reset", "en", {
            "first_name": "Alice",
            "reset_url": "http://localhost:3000/reset?token=abc",
        })
        assert "Alice" in html
        assert "http://localhost:3000/reset?token=abc" in html


class TestHighLevelEmails:
    """Subject and body rendering. The on/off gate is covered separately, so
    stub it open — these tests carry no organization row to switch anything on.
    """

    @pytest.fixture(autouse=True)
    def _templates_enabled(self):
        with patch("app.core.email._template_enabled", return_value=True):
            yield

    @patch("app.core.email.send_email", return_value=True)
    def test_send_welcome_email(self, mock_send):
        result = send_welcome_email("user@example.com", "Maria", "M-0001")
        assert result is True
        mock_send.assert_called_once()
        args = mock_send.call_args[0]
        assert args[0] == "user@example.com"
        assert "Maria" in args[2]
        assert "M-0001" in args[2]

    @patch("app.core.email.send_email", return_value=True)
    def test_send_welcome_email_ca(self, mock_send):
        result = send_welcome_email("user@example.com", "Joan", "M-0002", locale="ca")
        assert result is True
        subject = mock_send.call_args[0][1]
        assert "Benvingut" in subject

    @patch("app.core.email.send_email", return_value=True)
    def test_send_password_reset_email(self, mock_send):
        result = send_password_reset_email(
            "user@example.com", "Maria", "http://localhost:3000/reset?token=abc"
        )
        assert result is True
        mock_send.assert_called_once()
        assert "http://localhost:3000/reset?token=abc" in mock_send.call_args[0][2]

    @patch("app.core.email.send_email", return_value=True)
    def test_send_registration_confirmation(self, mock_send):
        result = send_registration_confirmation_email(
            "user@example.com", "Maria", "Yoga Workshop", "confirmed",
            activity_date="15/07/2026", location="Main Hall", locale="en",
        )
        assert result is True
        subject = mock_send.call_args[0][1]
        assert "Yoga Workshop" in subject
        assert "confirmed" in subject.lower()

    @patch("app.core.email.send_email", return_value=True)
    def test_send_registration_waitlisted(self, mock_send):
        result = send_registration_confirmation_email(
            "user@example.com", "Carlos", "Fútbol", "waitlist", locale="es",
        )
        assert result is True
        subject = mock_send.call_args[0][1]
        assert "lista de espera" in subject.lower()

    @patch("app.core.email.send_email", return_value=True)
    def test_send_cancellation(self, mock_send):
        result = send_registration_cancellation_email(
            "user@example.com", "Joan", "Natació", cancelled_by="Admin", locale="ca",
        )
        assert result is True
        subject = mock_send.call_args[0][1]
        assert "cancel·lada" in subject.lower()

    @patch("app.core.email.send_email", return_value=True)
    def test_send_waitlist_promotion(self, mock_send):
        result = send_waitlist_promotion_email(
            "user@example.com", "Bob", "Chess Club", locale="en",
        )
        assert result is True
        subject = mock_send.call_args[0][1]
        assert "Chess Club" in subject
