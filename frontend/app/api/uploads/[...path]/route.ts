import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8003";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const fullPath = path.map(encodeURIComponent).join("/");

  // The session cookie has to travel with the request: the API decides per
  // prefix who may read a stored file (member photos, mandates, registration
  // attachments), and answers 401/404 without it.
  const cookie = request.headers.get("cookie") || "";
  const res = await fetch(`${API_BASE_URL}/uploads/${fullPath}`, {
    headers: { Cookie: cookie },
  });

  if (!res.ok) {
    return new NextResponse(null, { status: res.status });
  }

  const contentType = res.headers.get("content-type") || "application/octet-stream";
  const buffer = await res.arrayBuffer();

  return new NextResponse(buffer, {
    status: 200,
    headers: {
      "Content-Type": contentType,
      "Content-Disposition": res.headers.get("content-disposition") || "attachment",
      "X-Content-Type-Options": "nosniff",
      // Private: most of what this proxies is one member's document, and a
      // shared cache must not hand it to the next visitor.
      "Cache-Control": res.headers.get("cache-control") || "private, max-age=3600",
    },
  });
}
