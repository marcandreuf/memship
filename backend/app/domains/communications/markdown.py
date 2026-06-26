"""Minimal, dependency-free Markdown → HTML renderer for announcement bodies.

The input is HTML-escaped first, then a small whitelist of Markdown constructs
(bold, italic, links, unordered lists, paragraphs / line breaks) is expanded.
Because escaping happens before any tag is emitted, authored HTML can never reach
the output — this is the sanitization boundary. The same renderer feeds the
member view and the email HTML.
"""

import html
import re

_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
_BOLD = re.compile(r"\*\*([^*\n]+)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_LIST_ITEM = re.compile(r"^\s*[-*]\s+")


def _inline(text: str) -> str:
    """Expand inline markers in already-escaped text."""
    text = _LINK.sub(r'<a href="\2">\1</a>', text)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _ITALIC.sub(r"<em>\1</em>", text)
    return text


def render_markdown(text: str) -> str:
    """Render a small, safe subset of Markdown to HTML."""
    escaped = html.escape(text or "", quote=False)
    blocks = re.split(r"\n\s*\n", escaped.strip())
    out: list[str] = []
    for block in blocks:
        lines = [ln for ln in block.split("\n") if ln.strip()]
        if lines and all(_LIST_ITEM.match(ln) for ln in lines):
            items = "".join(
                f"<li>{_inline(_LIST_ITEM.sub('', ln))}</li>" for ln in lines
            )
            out.append(f"<ul>{items}</ul>")
        elif lines:
            out.append("<p>" + "<br>".join(_inline(ln) for ln in lines) + "</p>")
    return "\n".join(out)


def excerpt(text: str, limit: int = 280) -> str:
    """Plain-text preview of a markdown body, collapsed and truncated."""
    plain = re.sub(r"[*_#>\[\]()]", "", text or "")
    plain = re.sub(r"^\s*[-]\s+", "", plain, flags=re.MULTILINE)
    plain = re.sub(r"\s+", " ", plain).strip()
    if len(plain) <= limit:
        return plain
    return plain[: limit - 1].rstrip() + "…"
