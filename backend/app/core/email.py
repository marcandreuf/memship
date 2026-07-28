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
from app.db import session as db_session
from app.domains.mailing.mailing_config import (
    ResolvedMailing,
    env_only_mailing_config,
    resolve_mailing_config,
)

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
    "booking_confirmation": {
        "es": "Reserva confirmada: {space}",
        "ca": "Reserva confirmada: {space}",
        "en": "Booking confirmed: {space}",
    },
    "booking_waitlisted": {
        "es": "En lista de espera: {space}",
        "ca": "En llista d'espera: {space}",
        "en": "You're on the waitlist: {space}",
    },
    "booking_promoted": {
        "es": "¡Plaza confirmada! {space}",
        "ca": "Plaça confirmada! {space}",
        "en": "You're in! {space}",
    },
    "booking_cancelled": {
        "es": "Reserva cancelada: {space}",
        "ca": "Reserva cancel·lada: {space}",
        "en": "Booking cancelled: {space}",
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
    "verification": {
        "es": "Confirma tu correo electrónico",
        "ca": "Confirma el teu correu electrònic",
        "en": "Confirm your email address",
    },
    "registration_approved": {
        "es": "Tu solicitud de alta ha sido aprobada",
        "ca": "La teva sol·licitud d'alta ha estat aprovada",
        "en": "Your registration has been approved",
    },
    "registration_rejected": {
        "es": "Sobre tu solicitud de alta",
        "ca": "Sobre la teva sol·licitud d'alta",
        "en": "About your registration request",
    },
    "payment_reminder": {
        "es": "Recordatorio de pago: recibo {receipt_number}",
        "ca": "Recordatori de pagament: rebut {receipt_number}",
        "en": "Payment reminder: receipt {receipt_number}",
    },
    "mailing_test": {
        "es": "Correo de prueba de Memship",
        "ca": "Correu de prova de Memship",
        "en": "Memship test email",
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
#
# The active provider and its credentials are resolved at send time from the DB
# (with an env-var fallback) via ``app.domains.mailing.mailing_config``. The
# module-level ``send_*`` API is unchanged for every caller; only the transport
# picks its credentials from the resolved config instead of ``settings`` directly.


def _resolve_transport() -> ResolvedMailing:
    """Resolve the active mail provider using a short-lived DB session.

    Callers (Celery tasks, request handlers, the billing reminder service) do
    not all carry a Session, so the transport opens its own for the one-row
    lookup. A settings save therefore applies on the next email with no restart.
    """
    try:
        db = db_session.SessionLocal()
    except Exception:  # noqa: BLE001 — never let mail config resolution break a send
        return env_only_mailing_config()
    try:
        return resolve_mailing_config(db)
    except Exception as e:  # noqa: BLE001 — degrade to env-only rather than failing the send
        logger.warning(f"Mailing config resolution failed, falling back to env: {e}")
        return env_only_mailing_config()
    finally:
        db.close()


def _send_via_resend(
    to: str,
    subject: str,
    html_body: str,
    api_key: str,
    from_email: str,
    attachment: bytes | None = None,
    attachment_filename: str = "document.pdf",
    attachment_mime: str = "application/pdf",
    raise_errors: bool = False,
) -> bool:
    """Send email via the Resend API with explicit credentials."""
    try:
        import resend
        resend.api_key = api_key
        payload: dict = {
            "from": from_email,
            "to": [to],
            "subject": subject,
            "html": html_body,
        }
        if attachment is not None:
            payload["attachments"] = [{
                "filename": attachment_filename,
                "content": list(attachment),
                "content_type": attachment_mime,
            }]
        resend.Emails.send(payload)
        logger.info(f"Email sent via Resend: to={to}, subject={subject}")
        return True
    except Exception as e:
        logger.error(f"Resend email failed: to={to}, error={e}")
        if raise_errors:
            raise
        return False


def _send_via_smtp(
    to: str,
    subject: str,
    html_body: str,
    host: str,
    port: int,
    tls: bool,
    user: str,
    password: str,
    from_email: str,
    attachment: bytes | None = None,
    attachment_filename: str = "document.pdf",
    attachment_mime: str = "application/pdf",
    raise_errors: bool = False,
) -> bool:
    """Send email via SMTP with explicit connection parameters."""
    if attachment is None:
        msg = MIMEMultipart("alternative")
    else:
        msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    if attachment is not None:
        from email.mime.base import MIMEBase
        from email import encoders

        part = MIMEBase(*attachment_mime.split("/"))
        part.set_payload(attachment)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{attachment_filename}"')
        msg.attach(part)

    try:
        with smtplib.SMTP(host, port) as server:
            if tls:
                server.starttls()
            if user and password:
                server.login(user, password)
            server.sendmail(from_email, to, msg.as_string())
        logger.info(f"Email sent via SMTP: to={to}, subject={subject}")
        return True
    except Exception as e:
        logger.error(f"SMTP email failed: to={to}, error={e}")
        if raise_errors:
            raise
        return False


def _dispatch(
    provider: str,
    resolved: ResolvedMailing,
    to: str,
    subject: str,
    html_body: str,
    attachment: bytes | None = None,
    attachment_filename: str = "document.pdf",
    attachment_mime: str = "application/pdf",
    raise_errors: bool = False,
) -> bool:
    """Send through a specific resolved provider (Resend or Gmail/SMTP)."""
    if provider == "resend":
        c = resolved.resend
        return _send_via_resend(
            to, subject, html_body,
            api_key=c.get("api_key"),
            from_email=c.get("from_email") or settings.SMTP_FROM,
            attachment=attachment,
            attachment_filename=attachment_filename,
            attachment_mime=attachment_mime,
            raise_errors=raise_errors,
        )
    if provider == "gmail":
        g = resolved.gmail
        host, port, tls = resolved.gmail_smtp()
        return _send_via_smtp(
            to, subject, html_body,
            host=host, port=port, tls=tls,
            user=g.get("user"),
            password=g.get("app_password"),
            from_email=g.get("from_email") or g.get("user"),
            attachment=attachment,
            attachment_filename=attachment_filename,
            attachment_mime=attachment_mime,
            raise_errors=raise_errors,
        )
    return False


def send_email(to: str, subject: str, html_body: str) -> bool:
    """Send an email through the active mail provider."""
    resolved = _resolve_transport()
    if not resolved.active:
        logger.info(f"Email skipped (no transport): to={to}, subject={subject}")
        return False
    return _dispatch(resolved.active, resolved, to, subject, html_body)


def send_email_with_attachment(
    to: str,
    subject: str,
    html_body: str,
    attachment: bytes,
    attachment_filename: str = "document.pdf",
    attachment_mime: str = "application/pdf",
) -> bool:
    """Send an email with a file attachment through the active mail provider."""
    resolved = _resolve_transport()
    if not resolved.active:
        logger.info(
            f"Email with attachment skipped (no transport): to={to}, "
            f"subject={subject}, file={attachment_filename}"
        )
        return False
    return _dispatch(
        resolved.active, resolved, to, subject, html_body,
        attachment=attachment,
        attachment_filename=attachment_filename,
        attachment_mime=attachment_mime,
    )


def send_test_email(resolved: ResolvedMailing, provider: str, to: str, locale: str = "es") -> tuple[bool, str | None]:
    """Send a test message through a specific provider, bypassing ``active``.

    Used by the settings screen so a superadmin can verify credentials before
    switching the active provider to them. Returns ``(ok, error)`` where a
    transport failure surfaces as a sanitized message rather than raising.
    """
    subject = _get_subject("mailing_test", locale)
    html_body = render_template("mailing_test", locale, {"provider": provider})
    try:
        ok = _dispatch(provider, resolved, to, subject, html_body, raise_errors=True)
        return (True, None) if ok else (False, "send_failed")
    except Exception as e:  # noqa: BLE001 — surface the transport error to the UI
        return False, str(e)


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


def send_verification_email(
    to: str, first_name: str, verification_url: str, locale: str = "es"
) -> bool:
    subject = _get_subject("verification", locale)
    html_body = render_template("verification", locale, {
        "first_name": first_name,
        "verification_url": verification_url,
    })
    return send_email(to, subject, html_body)


def send_registration_approved_email(
    to: str,
    first_name: str,
    member_number: str,
    login_url: str,
    locale: str = "es",
) -> bool:
    subject = _get_subject("registration_approved", locale)
    html_body = render_template("registration_approved", locale, {
        "first_name": first_name,
        "member_number": member_number,
        "login_url": login_url,
    })
    return send_email(to, subject, html_body)


def send_registration_rejected_email(
    to: str, first_name: str, reason: str | None = None, locale: str = "es"
) -> bool:
    subject = _get_subject("registration_rejected", locale)
    html_body = render_template("registration_rejected", locale, {
        "first_name": first_name,
        "reason": reason,
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


def send_payment_reminder_email(
    to: str,
    member_name: str,
    receipt_number: str,
    amount: str,
    currency: str,
    due_date: str,
    days_overdue: int,
    org_name: str,
    pay_now_url: str | None = None,
    bank_details: str | None = None,
    locale: str = "es",
) -> bool:
    """Send a payment reminder for an overdue receipt."""
    subject = _get_subject("payment_reminder", locale, receipt_number=receipt_number)
    html_body = render_template("payment_reminder", locale, {
        "member_name": member_name,
        "receipt_number": receipt_number,
        "amount": amount,
        "currency": currency,
        "due_date": due_date,
        "days_overdue": days_overdue,
        "org_name": org_name,
        "pay_now_url": pay_now_url,
        "bank_details": bank_details,
    })
    return send_email(to, subject, html_body)


def send_booking_confirmation_email(
    to: str,
    member_name: str,
    space_name: str,
    booking_date: str,
    booking_time: str,
    cancellation_deadline_hours: int | None = None,
    locale: str = "es",
) -> bool:
    """Confirm a member's booking of a slot-instance."""
    subject = _get_subject("booking_confirmation", locale, space=space_name)
    html_body = render_template("booking_confirmation", locale, {
        "member_name": member_name,
        "space_name": space_name,
        "booking_date": booking_date,
        "booking_time": booking_time,
        "cancellation_deadline_hours": cancellation_deadline_hours,
    })
    return send_email(to, subject, html_body)


def send_booking_waitlisted_email(
    to: str,
    member_name: str,
    space_name: str,
    booking_date: str,
    booking_time: str,
    position: int | None = None,
    locale: str = "es",
) -> bool:
    """Tell a member their booking is on the waitlist."""
    subject = _get_subject("booking_waitlisted", locale, space=space_name)
    html_body = render_template("booking_waitlisted", locale, {
        "member_name": member_name,
        "space_name": space_name,
        "booking_date": booking_date,
        "booking_time": booking_time,
        "position": position,
    })
    return send_email(to, subject, html_body)


def send_booking_promoted_email(
    to: str,
    member_name: str,
    space_name: str,
    booking_date: str,
    booking_time: str,
    locale: str = "es",
) -> bool:
    """Tell a member a spot opened and they are now booked."""
    subject = _get_subject("booking_promoted", locale, space=space_name)
    html_body = render_template("booking_promoted", locale, {
        "member_name": member_name,
        "space_name": space_name,
        "booking_date": booking_date,
        "booking_time": booking_time,
    })
    return send_email(to, subject, html_body)


def send_booking_cancelled_email(
    to: str,
    member_name: str,
    space_name: str,
    booking_date: str,
    booking_time: str,
    locale: str = "es",
) -> bool:
    """Tell a member the club cancelled their booking (admin cancel, or the
    slot/space was removed)."""
    subject = _get_subject("booking_cancelled", locale, space=space_name)
    html_body = render_template("booking_cancelled", locale, {
        "member_name": member_name,
        "space_name": space_name,
        "booking_date": booking_date,
        "booking_time": booking_time,
    })
    return send_email(to, subject, html_body)


def send_announcement_email(
    to: str,
    subject: str,
    body_html: str,
    org_name: str,
    locale: str = "es",
) -> bool:
    """Send a broadcast announcement.

    The email subject is the announcement's own subject. ``body_html`` is the
    pre-rendered, sanitized markdown body (see ``communications.markdown``).
    """
    html_body = render_template("announcement", locale, {
        "subject": subject,
        "body_html": body_html,
        "org_name": org_name,
    })
    return send_email(to, subject, html_body)
