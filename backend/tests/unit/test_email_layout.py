"""The shared email layout, its branding resolver and the plain-text part.

Content assertions live in ``test_email.py`` and ``test_booking_emails.py``;
what this file covers is the chrome those tests do not look at — that a rendered
email is a complete HTML document, that branding degrades instead of raising,
and that both transports ship a text alternative alongside the HTML.
"""

from email import message_from_string
from unittest.mock import MagicMock, patch

import pytest

from app.core import email as email_module
from app.core.email import _LAYOUT_STRINGS, render_template, send_email
from app.core.email_branding import (
    DEFAULT_COLOR,
    DEFAULT_NAME,
    ON_DARK,
    ON_LIGHT,
    EmailBranding,
    absolute_logo_url,
    get_email_branding,
    normalize_color,
    normalize_website,
    readable_on,
    reset_branding_cache,
)
from app.core.email_text import html_to_text
from app.domains.communications.markdown import render_markdown
from app.domains.mailing.mailing_config import ResolvedMailing, ResolvedProvider

BRANDING = EmailBranding(
    name="Club Sant Jordi",
    logo_url="https://club.test/uploads/org/logo.png",
    color="#0083ad",
    on_color="#ffffff",
    email="hola@club.test",
    phone="+34 900 000 000",
    website="https://club.test",
    website_label="club.test",
)

WELCOME = {"first_name": "María", "member_number": "SJ-0042"}


@pytest.fixture(autouse=True)
def _clean_branding_cache():
    reset_branding_cache()
    yield
    reset_branding_cache()


@pytest.fixture
def branded():
    """Render with a fixed organisation instead of whatever the DB holds."""
    with patch.object(email_module, "get_email_branding", return_value=BRANDING):
        yield BRANDING


def _resolved_gmail():
    def provider(name, values):
        return ResolvedProvider(
            name=name,
            values=values,
            sources={k: "db" for k in values},
            secret_flags={},
        )

    return ResolvedMailing(
        active="gmail",
        resend=provider("resend", {}),
        gmail=provider(
            "gmail", {"user": "club@gmail.com", "app_password": "pw", "from_email": "club@gmail.com"}
        ),
    )


class TestTheRenderedEmailIsACompleteDocument:
    @pytest.mark.parametrize("locale", ["es", "ca", "en"])
    def test_it_is_a_full_html_document(self, branded, locale):
        html = render_template("welcome", locale, dict(WELCOME))

        assert html.lstrip().startswith("<!DOCTYPE html")
        assert html.rstrip().endswith("</html>")
        assert '<meta charset="UTF-8">' in html
        assert f'<html lang="{locale}">' in html

    def test_it_declares_viewport_and_colour_scheme(self, branded):
        html = render_template("welcome", "es", dict(WELCOME))

        assert 'name="viewport"' in html
        assert 'name="color-scheme" content="light dark"' in html
        assert "prefers-color-scheme: dark" in html

    @pytest.mark.parametrize("locale", ["es", "ca", "en"])
    def test_it_signs_off_with_the_platform_name_in_english(self, branded, locale):
        """The signature is a product name, never translated."""
        html = render_template("welcome", locale, dict(WELCOME))

        assert "Powered by " in html
        assert 'href="https://openmemship.com/"' in html
        assert 'target="_blank" rel="noopener noreferrer"' in html
        assert html.index("Powered by ") > html.index(
            _LAYOUT_STRINGS[locale]["automated_notice"]
        )

    def test_the_layout_falls_back_to_es_with_the_content(self, branded):
        """An unknown locale must not lose the chrome along with the copy."""
        html = render_template("welcome", "fr", dict(WELCOME))

        assert "Bienvenido" in html
        assert _LAYOUT_STRINGS["es"]["automated_notice"] in html
        assert '<html lang="es">' in html


class TestBrandingReachesTheChrome:
    def test_header_and_footer_carry_the_organisation(self, branded):
        html = render_template("welcome", "es", dict(WELCOME))

        assert html.count("Club Sant Jordi") >= 2  # header text + footer
        assert "hola@club.test" in html
        assert "+34 900 000 000" in html
        assert "club.test" in html
        assert _LAYOUT_STRINGS["es"]["automated_notice"] in html

    def test_the_logo_is_rendered_with_the_name_as_text(self, branded):
        """Images are blocked by default for unknown senders, so the name can
        never be carried by the logo alone."""
        html = render_template("welcome", "es", dict(WELCOME))

        assert '<img src="https://club.test/uploads/org/logo.png"' in html
        assert 'alt="Club Sant Jordi"' in html
        assert ">Club Sant Jordi</span>" in html

    def test_without_a_logo_the_header_still_names_the_club(self):
        with patch.object(
            email_module,
            "get_email_branding",
            return_value=EmailBranding(name="Club Sant Jordi"),
        ):
            html = render_template("welcome", "es", dict(WELCOME))

        assert "<img" not in html
        assert "Club Sant Jordi" in html

    def test_the_brand_colour_paints_the_header_band(self, branded):
        html = render_template("welcome", "es", dict(WELCOME))

        assert "background-color:#0083ad" in html

    def test_a_cta_button_offers_a_copyable_fallback(self, branded):
        """The button's href, plus a fallback link whose text is the URL itself,
        so a client that strips the button still leaves something to copy."""
        url = "https://club.test/reset?token=abc"
        html = render_template(
            "password_reset", "es", {"first_name": "María", "reset_url": url}
        )

        assert html.count(f'href="{url}"') == 2
        assert f">{url}</a>" in html
        assert _LAYOUT_STRINGS["es"]["button_fallback"] in html

    def test_every_template_stays_well_under_the_gmail_clip(self, branded):
        """Gmail clips around 102 KB and hides the footer behind a link."""
        html = render_template(
            "payment_reminder",
            "es",
            {
                "member_name": "María Puig",
                "receipt_number": "INV-2026-0117",
                "amount": "85.00",
                "currency": "EUR",
                "due_date": "01/07/2026",
                "days_overdue": 14,
                "org_name": "Club Sant Jordi",
                "pay_now_url": "https://club.test/pay",
                "bank_details": None,
            },
        )

        assert len(html.encode("utf-8")) < 80_000


class TestBrandingResolution:
    def test_a_missing_organisation_row_yields_defaults(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("app.db.session.SessionLocal", return_value=db):
            branding = get_email_branding()

        assert branding.name == DEFAULT_NAME
        assert branding.color == DEFAULT_COLOR
        assert branding.logo_url is None

    def test_a_broken_session_degrades_instead_of_raising(self):
        """A DB hiccup must not turn a password reset into a 500."""
        with patch("app.db.session.SessionLocal", side_effect=RuntimeError("no db")):
            branding = get_email_branding()

        assert branding.name == DEFAULT_NAME

    def test_the_result_is_cached_between_calls(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("app.db.session.SessionLocal", return_value=db) as session:
            get_email_branding()
            get_email_branding()

        assert session.call_count == 1


class TestHeaderTextStaysReadable:
    def test_white_on_a_dark_brand_colour(self):
        assert readable_on("#0083ad") == ON_DARK
        assert readable_on("#101820") == ON_DARK

    def test_dark_text_on_a_pale_brand_colour(self):
        """A yellow club colour must not produce invisible white text."""
        assert readable_on("#ffe066") == ON_LIGHT
        assert readable_on("#ffffff") == ON_LIGHT

    @pytest.mark.parametrize("value", [None, "", "not-a-colour", "#12345"])
    def test_an_unusable_colour_falls_back_to_the_product_default(self, value):
        assert normalize_color(value) == DEFAULT_COLOR

    def test_short_hex_is_expanded(self):
        assert normalize_color("#0af") == "#00aaff"


class TestLogoUrls:
    def test_a_stored_path_becomes_absolute(self):
        with patch("app.core.email_branding.settings") as s:
            s.BACKEND_PUBLIC_URL = "https://api.club.test/"
            assert (
                absolute_logo_url("/uploads/org/logo.png")
                == "https://api.club.test/uploads/org/logo.png"
            )

    def test_a_localhost_base_yields_no_logo(self):
        """A link the recipient could never resolve is worse than no image."""
        with patch("app.core.email_branding.settings") as s:
            s.BACKEND_PUBLIC_URL = "http://localhost:8003"
            assert absolute_logo_url("/uploads/org/logo.png") is None

    def test_an_already_absolute_url_passes_through(self):
        assert (
            absolute_logo_url("https://cdn.club.test/logo.png")
            == "https://cdn.club.test/logo.png"
        )

    def test_no_stored_logo_yields_none(self):
        assert absolute_logo_url(None) is None


class TestWebsiteNormalisation:
    def test_a_scheme_is_added_and_the_label_drops_it(self):
        assert normalize_website("club.test") == ("https://club.test", "club.test")

    def test_an_existing_scheme_is_kept(self):
        assert normalize_website("http://club.test/") == ("http://club.test/", "club.test")

    def test_blank_yields_nothing(self):
        assert normalize_website("  ") == (None, None)


class TestThePlainTextAlternative:
    def test_it_carries_the_message_without_markup(self, branded):
        html = render_template("welcome", "es", dict(WELCOME))
        text = html_to_text(html)

        assert "<" not in text
        assert "María" in text
        assert "SJ-0042" in text
        assert "Club Sant Jordi" in text

    def test_the_hidden_preheader_and_its_padding_are_dropped(self, branded):
        html = render_template("welcome", "es", dict(WELCOME))
        text = html_to_text(html)

        assert "Tu cuenta de socio ya está activa." not in text
        assert "‌" not in text
        assert "͏" not in text

    def test_a_link_keeps_its_destination(self, branded):
        url = "https://club.test/verify?token=abc"
        html = render_template(
            "verification", "en", {"first_name": "María", "verification_url": url}
        )
        text = html_to_text(html)

        assert url in text
        assert "Confirm my email" in text

    def test_styles_and_scripts_never_leak_into_the_text(self, branded):
        html = render_template("welcome", "es", dict(WELCOME))
        text = html_to_text(html)

        assert "prefers-color-scheme" not in text
        assert "background-color" not in text

    def test_empty_input_is_handled(self):
        assert html_to_text("") == ""


class TestBothTransportsShipTheTextPart:
    @patch("app.core.email._resolve_transport")
    @patch("app.core.email.smtplib.SMTP")
    def test_smtp_sends_text_first_then_html(self, mock_smtp_class, mock_resolve):
        """In multipart/alternative the last part wins, so HTML must come second."""
        mock_resolve.return_value = _resolved_gmail()
        server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = server

        assert send_email("m@club.test", "Test", "<p>Hola María</p>") is True

        raw = server.sendmail.call_args[0][2]
        parts = message_from_string(raw).get_payload()
        assert [p.get_content_type() for p in parts] == ["text/plain", "text/html"]
        assert "Hola María" in parts[0].get_payload(decode=True).decode("utf-8")

    @patch("app.core.email._resolve_transport")
    def test_resend_payload_has_both_bodies(self, mock_resolve):
        mock_resolve.return_value = ResolvedMailing(
            active="resend",
            resend=ResolvedProvider(
                name="resend",
                values={"api_key": "re_key", "from_email": "no@club.test"},
                sources={},
                secret_flags={},
            ),
            gmail=ResolvedProvider(name="gmail", values={}, sources={}, secret_flags={}),
        )
        sent = {}

        class _Emails:
            @staticmethod
            def send(payload):
                sent.update(payload)

        with patch.dict("sys.modules", {"resend": MagicMock(Emails=_Emails)}):
            assert send_email("m@club.test", "Test", "<p>Hola</p>") is True

        assert sent["html"] == "<p>Hola</p>"
        assert sent["text"] == "Hola"


class TestAnnouncementBodiesCarryInlineStyles:
    def test_the_web_rendering_is_unchanged(self):
        assert render_markdown("**b**") == "<p><strong>b</strong></p>"

    def test_the_email_rendering_styles_the_tags_it_emits(self):
        html = render_markdown("hola", link_color="#0083ad")

        assert html.startswith("<p style=")
        assert "font-family:Helvetica" in html

    def test_links_take_the_brand_colour(self):
        html = render_markdown("[x](https://club.test/)", link_color="#0083ad")

        assert 'style="color:#0083ad;' in html
        assert 'href="https://club.test/"' in html

    def test_lists_are_styled_too(self):
        html = render_markdown("- one\n- two", link_color="#0083ad")

        assert "<ul style=" in html
        assert "<li style=" in html

    @pytest.mark.parametrize(
        "payload",
        [
            "<script>alert(1)</script>",
            '<img src=x onerror="alert(1)">',
            '[x](https://a.test/b"onmouseover="alert(1))',
        ],
    )
    def test_the_escape_boundary_holds_with_styling_on(self, payload):
        """Styling only decorates tags the renderer emits; author input must
        still never reach a tag position."""
        html = render_markdown(payload, link_color="#0083ad")

        assert "<script" not in html
        assert "<img" not in html
        assert 'onmouseover="' not in html
