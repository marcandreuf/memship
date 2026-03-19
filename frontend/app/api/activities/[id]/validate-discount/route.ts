import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8003";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const cookie = request.headers.get("cookie") || "";
  const searchParams = request.nextUrl.searchParams.toString();
  const body = await request.json();
  const url = `${API_BASE_URL}/api/v1/activities/${id}/validate-discount${searchParams ? `?${searchParams}` : ""}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Cookie: cookie },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
