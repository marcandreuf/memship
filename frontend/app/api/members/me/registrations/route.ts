import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8003";

export async function GET(request: NextRequest) {
  const cookie = request.headers.get("cookie") || "";
  const searchParams = request.nextUrl.searchParams.toString();
  const url = `${API_BASE_URL}/api/v1/members/me/registrations${searchParams ? `?${searchParams}` : ""}`;
  const res = await fetch(url, { headers: { Cookie: cookie } });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
