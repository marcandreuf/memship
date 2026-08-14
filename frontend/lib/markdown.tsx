/**
 * Minimal, safe Markdown → HTML for announcement bodies. Mirrors the backend
 * renderer (app/domains/communications/markdown.py): the text is HTML-escaped
 * first, then a small whitelist (bold, italic, links, unordered lists,
 * paragraphs / line breaks) is expanded — so authored HTML can never reach the
 * output. This is the sanitization boundary that makes the rendered output safe
 * to inject via dangerouslySetInnerHTML.
 *
 * The quote characters are part of that boundary: the link rule puts the
 * captured URL inside a quoted href, and the URL pattern excludes whitespace
 * and ")" but not '"'. While escapeHtml left quotes alone,
 * [x](https://a.test/b"onmouseover="alert(1)) closed the attribute and opened
 * an event handler instead.
 */

const LINK = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;
const BOLD = /\*\*([^*\n]+)\*\*/g;
const ITALIC = /(?<!\*)\*([^*\n]+)\*(?!\*)/g;
const LIST_ITEM = /^\s*[-*]\s+/;

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function inline(s: string): string {
  return s
    .replace(LINK, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    .replace(BOLD, "<strong>$1</strong>")
    .replace(ITALIC, "<em>$1</em>");
}

export function renderMarkdown(text: string): string {
  const escaped = escapeHtml(text || "").trim();
  const blocks = escaped.split(/\n\s*\n/);
  const out: string[] = [];
  for (const block of blocks) {
    const lines = block.split("\n").filter((l) => l.trim());
    if (lines.length && lines.every((l) => LIST_ITEM.test(l))) {
      out.push(
        "<ul>" +
          lines.map((l) => `<li>${inline(l.replace(LIST_ITEM, ""))}</li>`).join("") +
          "</ul>"
      );
    } else if (lines.length) {
      out.push("<p>" + lines.map(inline).join("<br>") + "</p>");
    }
  }
  return out.join("\n");
}

export function Markdown({
  content,
  className,
}: {
  content: string;
  className?: string;
}) {
  return (
    <div
      className={className}
      // Safe: renderMarkdown escapes all HTML before whitelisting markdown.
      dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
    />
  );
}
