"""Unit tests for email service."""

from unittest.mock import MagicMock, patch

from app.core.email import send_email, send_password_reset_email, send_welcome_email


class TestEmailService:
    @patch("app.core.email.settings")
    def test_send_email_disabled(self, mock_settings):
        mock_settings.smtp_enabled = False
        result = send_email("test@example.com", "Test", "<p>body</p>")
        assert result is False

    @patch("app.core.email.settings")
    @patch("app.core.email.smtplib.SMTP")
    def test_send_email_success(self, mock_smtp_class, mock_settings):
        mock_settings.smtp_enabled = True
        mock_settings.SMTP_HOST = "smtp.example.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.SMTP_TLS = True
        mock_settings.SMTP_USER = "user"
        mock_settings.SMTP_PASSWORD = "pass"
        mock_settings.SMTP_FROM = "noreply@example.com"

        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        result = send_email("test@example.com", "Test Subject", "<p>Hello</p>")

        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user", "pass")
        mock_server.sendmail.assert_called_once()
        mock_server.quit.assert_called_once()

    @patch("app.core.email.settings")
    @patch("app.core.email.smtplib.SMTP")
    def test_send_email_failure(self, mock_smtp_class, mock_settings):
        mock_settings.smtp_enabled = True
        mock_settings.SMTP_HOST = "smtp.example.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.SMTP_TLS = False
        mock_settings.SMTP_USER = ""
        mock_settings.SMTP_PASSWORD = ""
        mock_settings.SMTP_FROM = "noreply@example.com"

        mock_smtp_class.side_effect = ConnectionRefusedError("Connection refused")

        result = send_email("test@example.com", "Test", "<p>body</p>")
        assert result is False

    @patch("app.core.email.send_email", return_value=True)
    def test_send_welcome_email(self, mock_send):
        result = send_welcome_email("user@example.com", "Maria", "M-0001")
        assert result is True
        mock_send.assert_called_once()
        args = mock_send.call_args
        assert "user@example.com" == args[0][0]
        assert "Maria" in args[0][2]
        assert "M-0001" in args[0][2]

    @patch("app.core.email.send_email", return_value=True)
    def test_send_password_reset_email(self, mock_send):
        result = send_password_reset_email(
            "user@example.com", "Maria", "http://localhost:3000/reset?token=abc"
        )
        assert result is True
        mock_send.assert_called_once()
        args = mock_send.call_args
        assert "http://localhost:3000/reset?token=abc" in args[0][2]
