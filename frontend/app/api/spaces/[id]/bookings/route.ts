import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8003";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const cookie = request.headers.get("cookie") || "";
  const search = request.nextUrl.searchParams.toString();
  const res = await fetch(
    `${API_BASE_URL}/api/v1/spaces/${id}/bookings${search ? `?${search}` : ""}`,
    { headers: { Cookie: cookie } }
  );
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
