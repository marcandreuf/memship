"""The announcement renderer is a sanitization boundary, so test it as one.

`render_markdown` output goes straight into `dangerouslySetInnerHTML` on the
member view and into the announcement email HTML, with nothing downstream to
catch a stray tag. Authoring needs `communications.write`, so anything that
escapes here is a limited staff role reaching a super admin's session.
"""

import pytest

from app.domains.communications.markdown import excerpt, render_markdown


class TestQuotesCannotBreakOutOfTheHrefAttribute:
    def test_a_quote_in_a_link_url_does_not_open_an_event_handler(self):
        """The regression. The URL pattern excludes whitespace and ")" but not
        '"', and the capture lands inside a quoted href."""
        html = render_markdown('[click](https://x.test/a"onmouseover="alert(1))')

        # The word itself survives as text inside the attribute value, which is
        # harmless. What must not appear is the unescaped quote that would end
        # the href and start a new attribute.
        assert 'onmouseover="' not in html
        assert '<a href="https://x.test/a&quot;onmouseover=&quot;alert(1">' in html

    def test_a_quote_in_body_text_is_escaped(self):
        html = render_markdown('say "hello"')

        assert '"' not in html
        assert "&quot;hello&quot;" in html

    def test_a_single_quote_is_escaped_too(self):
        html = render_markdown("it's here")

        assert "'" not in html
        assert "&#x27;" in html

    def test_a_quote_in_link_text_cannot_reopen_the_tag(self):
        html = render_markdown('[a" onmouseover="alert(1)](https://x.test/)')

        assert "onmouseover=&quot;" in html
        assert 'onmouseover="' not in html


class TestAuthoredHtmlNeverReachesTheOutput:
    @pytest.mark.parametrize(
        "payload",
        [
            "<script>alert(1)</script>",
            "<img src=x onerror=alert(1)>",
            "<a href='javascript:alert(1)'>x</a>",
            "<iframe src='https://evil.test'></iframe>",
        ],
    )
    def test_tags_are_escaped_not_emitted(self, payload):
        """The payload may survive as visible text — that is the point of
        escaping. What must not survive is a tag the browser parses."""
        html = render_markdown(payload)

        assert "&lt;" in html
        for tag in ("<script", "<img", "<iframe", "<a href='"):
            assert tag not in html

    def test_only_http_urls_become_links(self):
        """The pattern requires a http(s) scheme, so javascript: stays text."""
        html = render_markdown("[x](javascript:alert(1))")

        assert "<a " not in html


class TestTheMarkdownSubsetStillWorks:
    def test_a_plain_link_renders(self):
        assert (
            render_markdown("[home](https://memship.test/a)")
            == '<p><a href="https://memship.test/a">home</a></p>'
        )

    def test_an_ampersand_in_a_url_survives_as_an_entity(self):
        """`&` escapes to `&amp;` inside the attribute, which is how a literal
        `&` is spelled there — the browser requests `?a=1&b=2`."""
        html = render_markdown("[q](https://x.test/?a=1&b=2)")

        assert 'href="https://x.test/?a=1&amp;b=2"' in html

    def test_bold_italic_and_lists(self):
        assert render_markdown("**b**") == "<p><strong>b</strong></p>"
        assert render_markdown("*i*") == "<p><em>i</em></p>"
        assert render_markdown("- one\n- two") == "<ul><li>one</li><li>two</li></ul>"

    def test_paragraphs_and_line_breaks(self):
        assert render_markdown("a\nb\n\nc") == "<p>a<br>b</p>\n<p>c</p>"

    def test_empty_input_renders_nothing(self):
        assert render_markdown("") == ""


class TestExcerpt:
    def test_excerpt_is_plain_text_and_carries_no_markup(self):
        """Rendered as a React text node in the notification list, so it needs
        no escaping — but it must not carry markdown syntax into the preview."""
        text = excerpt("**bold** and <b>[a](https://x.test)</b>")

        assert not set("*[]()") & set(text)
        assert "bold" in text

    def test_excerpt_truncates_with_an_ellipsis(self):
        assert excerpt("x" * 400, limit=10) == "x" * 9 + "…"
