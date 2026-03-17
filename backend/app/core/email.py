"""Email service — sends emails via SMTP."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, html_body: str) -> bool:
    if not settings.smtp_enabled:
        logger.info(f"Email not sent (SMTP disabled): to={to}, subject={subject}")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    try:
        if settings.SMTP_TLS:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            server.starttls()
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)

        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

        server.sendmail(settings.SMTP_FROM, to, msg.as_string())
        server.quit()
        logger.info(f"Email sent: to={to}, subject={subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: to={to}, error={e}")
        return False


def send_welcome_email(to: str, first_name: str, member_number: str) -> bool:
    subject = "Bienvenido a Memship / Welcome to Memship"
    html_body = f"""
    <h2>Bienvenido, {first_name}!</h2>
    <p>Tu cuenta ha sido creada correctamente.</p>
    <p>Tu número de socio es: <strong>{member_number}</strong></p>
    <hr>
    <h2>Welcome, {first_name}!</h2>
    <p>Your account has been created successfully.</p>
    <p>Your member number is: <strong>{member_number}</strong></p>
    """
    return send_email(to, subject, html_body)


def send_password_reset_email(to: str, first_name: str, reset_url: str) -> bool:
    subject = "Restablecer contraseña / Reset your password"
    html_body = f"""
    <h2>Hola, {first_name}</h2>
    <p>Has solicitado restablecer tu contraseña. Haz clic en el siguiente enlace:</p>
    <p><a href="{reset_url}">{reset_url}</a></p>
    <p>Este enlace expira en 1 hora.</p>
    <hr>
    <h2>Hello, {first_name}</h2>
    <p>You requested a password reset. Click the link below:</p>
    <p><a href="{reset_url}">{reset_url}</a></p>
    <p>This link expires in 1 hour.</p>
    """
    return send_email(to, subject, html_body)
