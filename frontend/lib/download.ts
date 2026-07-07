/**
 * Trigger a browser download for a same-origin URL (e.g. a proxied CSV export).
 *
 * The server sets `Content-Disposition: attachment`, so navigating to the URL
 * downloads the streamed file rather than rendering it. Auth cookies are
 * HTTP-only and sent automatically with the same-origin request.
 */
export function downloadFile(
  path: string,
  params?: Record<string, string | number | undefined | null>
) {
  const query = new URLSearchParams();
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== "") {
        query.set(key, String(value));
      }
    }
  }
  const qs = query.toString();
  const url = qs ? `${path}?${qs}` : path;

  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}
