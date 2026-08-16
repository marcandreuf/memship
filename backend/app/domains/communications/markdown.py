"""Minimal, dependency-free Markdown → HTML renderer for announcement bodies.

The input is HTML-escaped first, then a small whitelist of Markdown constructs
(bold, italic, links, unordered lists, paragraphs / line breaks) is expanded.
Because escaping happens before any tag is emitted, authored HTML can never reach
the output — this is the sanitization boundary. The same renderer feeds the
member view and the email HTML.

Escaping the quote characters is part of that boundary, not a detail: the link
rule interpolates the captured URL *inside* a quoted ``href``, and the URL
pattern excludes whitespace and ``)`` but not ``"``. Escaping with
``quote=False`` therefore let an author close the attribute and open another
one — ``[x](https://a.test/b"onmouseover="alert(1))`` emitted a live event
handler. Authoring an announcement needs ``communications.write``, so that was
a route from a limited staff role to script running in a super admin's session.
"""

import html
import re

_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
_BOLD = re.compile(r"\*\*([^*\n]+)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_LIST_ITEM = re.compile(r"^\s*[-*]\s+")

# Email clients do not cascade styles the way a browser does, and several strip
# <style> blocks outright, so the email rendering of a body carries its styles
# inline. Only tags this renderer emits itself are styled; the escape boundary
# described above is untouched and author input never reaches a tag position.
_FONT = "font-family:Helvetica,Arial,sans-serif;"
_EMAIL_STYLES = {
    "p": f"margin:0 0 16px 0; {_FONT} font-size:16px; line-height:24px; mso-line-height-rule:exactly; color:#1f2328;",
    "ul": f"margin:0 0 16px 0; padding-left:20px; {_FONT} font-size:16px; line-height:24px; color:#1f2328;",
    "li": "margin:0 0 6px 0;",
    "a": "text-decoration:underline;",
}


def _style_attr(tag: str, link_color: str | None) -> str:
    """Inline ``style`` attribute for an emitted tag, or '' when styling is off."""
    if link_color is None:
        return ""
    style = _EMAIL_STYLES[tag]
    if tag == "a":
        style = f"color:{link_color}; {style}"
    return f' style="{style}"'


def _inline(text: str, link_color: str | None = None) -> str:
    """Expand inline markers in already-escaped text."""
    text = _LINK.sub(rf'<a{_style_attr("a", link_color)} href="\2">\1</a>', text)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _ITALIC.sub(r"<em>\1</em>", text)
    return text


def render_markdown(text: str, *, link_color: str | None = None) -> str:
    """Render a small, safe subset of Markdown to HTML.

    ``link_color`` opts into the email rendering: the emitted tags get inline
    styles and links take the organisation's brand colour. The member-facing web
    view leaves it unset and gets exactly the markup it always had.
    """
    escaped = html.escape(text or "")
    blocks = re.split(r"\n\s*\n", escaped.strip())
    out: list[str] = []
    for block in blocks:
        lines = [ln for ln in block.split("\n") if ln.strip()]
        if lines and all(_LIST_ITEM.match(ln) for ln in lines):
            items = "".join(
                f"<li{_style_attr('li', link_color)}>"
                f"{_inline(_LIST_ITEM.sub('', ln), link_color)}</li>"
                for ln in lines
            )
            out.append(f"<ul{_style_attr('ul', link_color)}>{items}</ul>")
        elif lines:
            out.append(
                f"<p{_style_attr('p', link_color)}>"
                + "<br>".join(_inline(ln, link_color) for ln in lines)
                + "</p>"
            )
    return "\n".join(out)


def excerpt(text: str, limit: int = 280) -> str:
    """Plain-text preview of a markdown body, collapsed and truncated."""
    plain = re.sub(r"[*_#>\[\]()]", "", text or "")
    plain = re.sub(r"^\s*[-]\s+", "", plain, flags=re.MULTILINE)
    plain = re.sub(r"\s+", " ", plain).strip()
    if len(plain) <= limit:
        return plain
    return plain[: limit - 1].rstrip() + "…"
