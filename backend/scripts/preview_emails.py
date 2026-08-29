"""Render every email template with fixture data, for eyeballing in a browser.

Email layout cannot be verified by reading the markup — the only useful check is
looking at it. This renders all templates × locales into a directory, plus an
index page, with branding stubbed so no database is needed:

    uv run python scripts/preview_emails.py            # → .preview/email/
    uv run python scripts/preview_emails.py --out DIR

It also fails loudly on any template that does not render, which makes it a
cheap syntax check over all 54 files after a layout change.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import email as email_module  # noqa: E402
from app.core import email_branding  # noqa: E402
from app.core.email_text import html_to_text  # noqa: E402

LOCALES = ("es", "ca", "en")

PREVIEW_BRANDING = email_branding.EmailBranding(
    name="Club Esportiu Sant Jordi",
    logo_url=None,
    color="#0083ad",
    on_color="#ffffff",
    email="hola@clubsantjordi.test",
    phone="+34 900 000 000",
    website="https://clubsantjordi.test",
    website_label="clubsantjordi.test",
)

# One context per template name. Optional fields are populated so the preview
# shows the fullest version of each email; drop a value to see the other branch.
CONTEXTS: dict[str, dict] = {
    "welcome": {"first_name": "María", "member_number": "SJ-0042"},
    "verification": {
        "first_name": "María",
        "verification_url": "https://clubsantjordi.test/verify?token=8f3c1d",
    },
    "password_reset": {
        "first_name": "María",
        "reset_url": "https://clubsantjordi.test/reset?token=8f3c1d",
    },
    "registration_approved": {
        "first_name": "María",
        "member_number": "SJ-0042",
        "login_url": "https://clubsantjordi.test/login",
    },
    "registration_rejected": {
        "first_name": "María",
        "reason": "La documentación aportada está incompleta.",
    },
    "registration_confirmed": {
        "member_name": "María Puig",
        "activity_name": "Iniciación al pádel",
        "activity_date": "15/07/2026 18:00",
        "location": "Pista 3",
    },
    "registration_waitlisted": {
        "member_name": "María Puig",
        "activity_name": "Iniciación al pádel",
        "activity_date": "15/07/2026 18:00",
        "location": "Pista 3",
    },
    "registration_cancelled": {
        "member_name": "María Puig",
        "activity_name": "Iniciación al pádel",
        "cancelled_by": "Secretaría del club",
    },
    "waitlist_promoted": {
        "member_name": "María Puig",
        "activity_name": "Iniciación al pádel",
        "activity_date": "15/07/2026 18:00",
        "location": "Pista 3",
    },
    "booking_confirmation": {
        "member_name": "María Puig",
        "space_name": "Pista 1",
        "booking_date": "15/07/2026",
        "booking_time": "18:00 – 19:30",
        "cancellation_deadline_hours": 12,
    },
    "booking_waitlisted": {
        "member_name": "María Puig",
        "space_name": "Pista 1",
        "booking_date": "15/07/2026",
        "booking_time": "18:00 – 19:30",
        "position": 2,
    },
    "booking_promoted": {
        "member_name": "María Puig",
        "space_name": "Pista 1",
        "booking_date": "15/07/2026",
        "booking_time": "18:00 – 19:30",
    },
    "booking_cancelled": {
        "member_name": "María Puig",
        "space_name": "Pista 1",
        "booking_date": "15/07/2026",
        "booking_time": "18:00 – 19:30",
    },
    "payment_reminder": {
        "member_name": "María Puig",
        "receipt_number": "INV-2026-0117",
        "amount": "85.00",
        "currency": "EUR",
        "due_date": "01/07/2026",
        "days_overdue": 14,
        "org_name": "Club Esportiu Sant Jordi",
        "pay_now_url": "https://clubsantjordi.test/pay/INV-2026-0117",
        "bank_details": None,
    },
    "announcement": {
        "subject": "Cierre por mantenimiento",
        "org_name": "Club Esportiu Sant Jordi",
        "body_html": None,  # filled in below with the real markdown renderer
    },
    "mailing_test": {"provider": "resend"},
    "receipt_delivery": {
        "member_name": "María",
        "receipt_number": "INV-2026-0117",
        "amount": "85.00",
        "currency": "EUR",
        "org_name": "Club Esportiu Sant Jordi",
    },
    "billing_summary": {
        "rows": [
            {"frequency": "monthly", "count": 128, "status": "success"},
            {"frequency": "quarterly", "count": 41, "status": "success"},
            {"frequency": "annual", "count": 0, "status": "failed"},
        ],
        "total": 169,
        "any_failed": True,
    },
}

# A second pass over templates whose optional branch is worth seeing on its own.
VARIANTS: dict[str, dict] = {
    "payment_reminder": {
        "pay_now_url": None,
        "bank_details": "Banc de Sabadell\nES91 2100 0418 4502 0005 1332\nBSAB ESBB",
    },
}


def _announcement_body() -> str:
    from app.domains.communications.markdown import render_markdown

    return render_markdown(
        "La piscina permanecerá **cerrada** del 1 al 5 de agosto por trabajos de "
        "mantenimiento.\n\n"
        "- El gimnasio mantiene su horario habitual\n"
        "- Las pistas exteriores no se ven afectadas\n\n"
        "Consulta el [calendario completo](https://clubsantjordi.test/calendario).",
        link_color=PREVIEW_BRANDING.color,
    )


def render_all(out_dir: Path) -> list[tuple[str, str, int]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    CONTEXTS["announcement"]["body_html"] = _announcement_body()

    written: list[tuple[str, str, int]] = []
    for name, base_context in CONTEXTS.items():
        cases = [("", base_context)]
        if name in VARIANTS:
            cases.append(("-alt", {**base_context, **VARIANTS[name]}))
        for suffix, context in cases:
            for locale in LOCALES:
                html = email_module.render_template(name, locale, dict(context))
                filename = f"{name}{suffix}_{locale}.html"
                (out_dir / filename).write_text(html, encoding="utf-8")
                (out_dir / f"{name}{suffix}_{locale}.txt").write_text(
                    html_to_text(html), encoding="utf-8"
                )
                written.append((filename, locale, len(html.encode("utf-8"))))
    return written


def write_index(out_dir: Path, written: list[tuple[str, str, int]]) -> None:
    rows = "\n".join(
        f'<tr><td><a href="{f}">{f}</a></td>'
        f'<td><a href="{f[:-5]}.txt">text</a></td>'
        f"<td>{size / 1024:.1f} KB</td></tr>"
        for f, _locale, size in written
    )
    (out_dir / "index.html").write_text(
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<title>Email previews</title>"
        "<style>body{font:14px system-ui;margin:2rem}"
        "td{padding:2px 12px 2px 0}</style></head>"
        f"<body><h1>Email previews</h1><table>{rows}</table></body></html>",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=Path(__file__).resolve().parent.parent / ".preview" / "email",
        type=Path,
        help="output directory (default: .preview/email)",
    )
    args = parser.parse_args()

    # Stub branding so the preview needs no database and stays reproducible.
    email_branding._cache = (float("inf"), PREVIEW_BRANDING)
    email_module.get_email_branding = lambda: PREVIEW_BRANDING

    written = render_all(args.out)
    write_index(args.out, written)

    largest = max(written, key=lambda w: w[2])
    print(f"Rendered {len(written)} previews into {args.out}")
    print(f"Largest: {largest[0]} at {largest[2] / 1024:.1f} KB")
    print(f"Open {args.out / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
