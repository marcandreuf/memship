import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8003";

export async function GET(request: NextRequest) {
  const cookie = request.headers.get("cookie") || "";
  const res = await fetch(`${API_BASE_URL}/api/v1/members/me/payment-method`, {
    headers: { Cookie: cookie },
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function PUT(request: NextRequest) {
  const cookie = request.headers.get("cookie") || "";
  const body = await request.json();
  const res = await fetch(`${API_BASE_URL}/api/v1/members/me/payment-method`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Cookie: cookie },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
