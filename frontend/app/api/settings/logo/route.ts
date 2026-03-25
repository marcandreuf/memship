import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8003";

export async function POST(request: NextRequest) {
  const cookie = request.headers.get("cookie") || "";
  const formData = await request.formData();
  const res = await fetch(`${API_BASE_URL}/api/v1/settings/logo/`, {
    method: "POST",
    headers: { Cookie: cookie },
    body: formData,
  });
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}

export async function DELETE(request: NextRequest) {
  const cookie = request.headers.get("cookie") || "";
  const res = await fetch(`${API_BASE_URL}/api/v1/settings/logo/`, {
    method: "DELETE",
    headers: { Cookie: cookie },
  });
  if (res.status === 204) {
    return new NextResponse(null, { status: 204 });
  }
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
