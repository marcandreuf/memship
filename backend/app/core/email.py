"""Email service — sends emails via Resend API or SMTP.

Transport priority:
  1. RESEND_API_KEY set → use Resend API (managed, best deliverability)
  2. SMTP_HOST set     → use SMTP (self-hosted)
  3. Neither           → log and skip (dev mode, no error)
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

from app.core.config import settings

logger = logging.getLogger(__name__)

# Jinja2 template environment
_template_dir = Path(__file__).resolve().parent.parent / "templates" / "email"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_template_dir)),
    autoescape=select_autoescape(["html"]),
)

# Email subject translations
_SUBJECTS = {
    "registration_confirmed": {
        "es": "Inscripción confirmada: {activity}",
        "ca": "Inscripció confirmada: {activity}",
        "en": "Registration confirmed: {activity}",
    },
    "registration_waitlisted": {
        "es": "En lista de espera: {activity}",
        "ca": "En llista d'espera: {activity}",
        "en": "You're on the waitlist: {activity}",
    },
    "registration_cancelled": {
        "es": "Inscripción cancelada: {activity}",
        "ca": "Inscripció cancel·lada: {activity}",
        "en": "Registration cancelled: {activity}",
    },
    "waitlist_promoted": {
        "es": "¡Plaza confirmada! {activity}",
        "ca": "Plaça confirmada! {activity}",
        "en": "You're in! {activity}",
    },
    "welcome": {
        "es": "Bienvenido a Memship",
        "ca": "Benvingut a Memship",
        "en": "Welcome to Memship",
    },
    "password_reset": {
        "es": "Restablecer contraseña",
        "ca": "Restablir contrasenya",
        "en": "Reset your password",
    },
}


def render_template(template_name: str, locale: str, context: dict) -> str:
    """Render a Jinja2 email template with locale fallback to 'es'."""
    for loc in [locale, "es"]:
        try:
            template = _jinja_env.get_template(f"{template_name}_{loc}.html")
            return template.render(**context)
        except TemplateNotFound:
            continue
    raise ValueError(f"Email template not found: {template_name}")


def _get_subject(template_name: str, locale: str, **kwargs) -> str:
    """Get localized subject line with fallback to 'es'."""
    subjects = _SUBJECTS.get(template_name, {})
    subject = subjects.get(locale, subjects.get("es", template_name))
    return subject.format(**kwargs) if kwargs else subject


# --- Transport layer ---

def _send_via_resend(to: str, subject: str, html_body: str) -> bool:
    """Send email via Resend API."""
    try:
        import resend
        resend.api_key = settings.RESEND_API_KEY
        from_email = settings.RESEND_FROM_EMAIL or settings.SMTP_FROM
        resend.Emails.send({
            "from": from_email,
            "to": [to],
            "subject": subject,
            "html": html_body,
        })
        logger.info(f"Email sent via Resend: to={to}, subject={subject}")
        return True
    except Exception as e:
        logger.error(f"Resend email failed: to={to}, error={e}")
        return False


def _send_via_smtp(to: str, subject: str, html_body: str) -> bool:
    """Send email via SMTP."""
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
        logger.info(f"Email sent via SMTP: to={to}, subject={subject}")
        return True
    except Exception as e:
        logger.error(f"SMTP email failed: to={to}, error={e}")
        return False


def send_email(to: str, subject: str, html_body: str) -> bool:
    """Send an email using the best available transport."""
    if settings.RESEND_API_KEY:
        return _send_via_resend(to, subject, html_body)
    elif settings.smtp_enabled:
        return _send_via_smtp(to, subject, html_body)
    else:
        logger.info(f"Email skipped (no transport): to={to}, subject={subject}")
        return False


# --- High-level email functions ---

def send_welcome_email(to: str, first_name: str, member_number: str, locale: str = "es") -> bool:
    subject = _get_subject("welcome", locale)
    html_body = render_template("welcome", locale, {
        "first_name": first_name,
        "member_number": member_number,
    })
    return send_email(to, subject, html_body)


def send_password_reset_email(to: str, first_name: str, reset_url: str, locale: str = "es") -> bool:
    subject = _get_subject("password_reset", locale)
    html_body = render_template("password_reset", locale, {
        "first_name": first_name,
        "reset_url": reset_url,
    })
    return send_email(to, subject, html_body)


def send_registration_confirmation_email(
    to: str,
    member_name: str,
    activity_name: str,
    status: str,
    activity_date: str | None = None,
    location: str | None = None,
    locale: str = "es",
) -> bool:
    template = "registration_confirmed" if status == "confirmed" else "registration_waitlisted"
    subject = _get_subject(template, locale, activity=activity_name)
    html_body = render_template(template, locale, {
        "member_name": member_name,
        "activity_name": activity_name,
        "activity_date": activity_date,
        "location": location,
    })
    return send_email(to, subject, html_body)


def send_registration_cancellation_email(
    to: str,
    member_name: str,
    activity_name: str,
    cancelled_by: str | None = None,
    locale: str = "es",
) -> bool:
    subject = _get_subject("registration_cancelled", locale, activity=activity_name)
    html_body = render_template("registration_cancelled", locale, {
        "member_name": member_name,
        "activity_name": activity_name,
        "cancelled_by": cancelled_by,
    })
    return send_email(to, subject, html_body)


def send_waitlist_promotion_email(
    to: str,
    member_name: str,
    activity_name: str,
    activity_date: str | None = None,
    location: str | None = None,
    locale: str = "es",
) -> bool:
    subject = _get_subject("waitlist_promoted", locale, activity=activity_name)
    html_body = render_template("waitlist_promoted", locale, {
        "member_name": member_name,
        "activity_name": activity_name,
        "activity_date": activity_date,
        "location": location,
    })
    return send_email(to, subject, html_body)
