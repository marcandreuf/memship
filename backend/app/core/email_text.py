"""Plain-text alternative derived from a rendered email.

Both transports used to ship HTML only — the SMTP path even built a
``multipart/alternative`` and attached a single part, which is the shape of a
multipart with a missing sibling and reads as a mild spam signal.

The text part is *derived*, not authored: 48 hand-written ``.txt`` companions
would double the translation surface for a part almost nobody reads, and would
drift from the HTML the first time a template changed.
"""

import html
import re

# Whole subtrees that carry no reader-facing text.
_DROP_BLOCKS = re.compile(
    r"<(head|style|script|title)\b[^>]*>.*?</\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
# The hidden inbox-preview line duplicates the body; it is tagged with a class
# precisely so this pass can find it.
_PREHEADER = re.compile(
    r'<div[^>]*class="[^"]*ms-preheader[^"]*"[^>]*>.*?</div\s*>',
    re.IGNORECASE | re.DOTALL,
)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_LINK = re.compile(r'<a\b[^>]*\bhref\s*=\s*"([^"]*)"[^>]*>(.*?)</a\s*>', re.IGNORECASE | re.DOTALL)
_LIST_ITEM = re.compile(r"<li\b[^>]*>", re.IGNORECASE)
_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)
_BLOCK_END = re.compile(
    r"</(p|div|td|tr|table|ul|ol|li|h1|h2|h3|h4|h5|h6|blockquote)\s*>",
    re.IGNORECASE,
)
_TAG = re.compile(r"<[^>]+>")
# Zero-width characters the layout uses to pad the inbox preview line.
_INVISIBLE = re.compile(
    "[" + "".join(chr(c) for c in (0x200B, 0x200C, 0x200D, 0x034F, 0xFEFF)) + "]"
)
_TRAILING_SPACE = re.compile(r"[ \t]+$", re.MULTILINE)
_BLANK_RUN = re.compile(r"\n{3,}")
_SPACE_RUN = re.compile(r"[ \t]{2,}")


def _link_replacement(match: re.Match[str]) -> str:
    href = match.group(1).strip()
    label = html.unescape(_TAG.sub("", match.group(2))).strip()
    if not href:
        return label
    if href.startswith("mailto:") and href[len("mailto:"):] == label:
        return label
    if not label or label == href:
        return href
    return f"{label} ({href})"


def html_to_text(rendered_html: str) -> str:
    """Render the plain-text alternative of an already-rendered email."""
    text = rendered_html or ""
    text = _COMMENT.sub("", text)
    text = _DROP_BLOCKS.sub("", text)
    text = _PREHEADER.sub("", text)
    text = _LINK.sub(_link_replacement, text)
    text = _LIST_ITEM.sub("\n- ", text)
    text = _BREAK.sub("\n", text)
    text = _BLOCK_END.sub("\n", text)
    text = _TAG.sub("", text)
    text = html.unescape(text)
    text = _INVISIBLE.sub("", text)
    text = text.replace("\xa0", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = _SPACE_RUN.sub(" ", text)
    text = _TRAILING_SPACE.sub("", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = _BLANK_RUN.sub("\n\n", text)
    return text.strip()