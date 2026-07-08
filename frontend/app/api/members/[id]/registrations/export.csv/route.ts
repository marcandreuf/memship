import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8003";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const cookie = request.headers.get("cookie") || "";
  const res = await fetch(
    `${API_BASE_URL}/api/v1/members/${id}/registrations/export.csv${request.nextUrl.search}`,
    { headers: { Cookie: cookie } }
  );
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: "Export failed" }));
    return NextResponse.json(data, { status: res.status });
  }
  return new NextResponse(res.body, {
    status: 200,
    headers: {
      "Content-Type": res.headers.get("Content-Type") || "text/csv; charset=utf-8",
      "Content-Disposition":
        res.headers.get("Content-Disposition") ||
        `attachment; filename="member-${id}-registrations.csv"`,
    },
  });
}
