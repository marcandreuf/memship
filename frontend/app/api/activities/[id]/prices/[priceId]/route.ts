import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8003";

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; priceId: string }> }
) {
  const { id, priceId } = await params;
  const cookie = request.headers.get("cookie") || "";
  const body = await request.json();
  const res = await fetch(`${API_BASE_URL}/api/v1/activities/${id}/prices/${priceId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Cookie: cookie },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; priceId: string }> }
) {
  const { id, priceId } = await params;
  const cookie = request.headers.get("cookie") || "";
  const res = await fetch(`${API_BASE_URL}/api/v1/activities/${id}/prices/${priceId}`, {
    method: "DELETE",
    headers: { Cookie: cookie },
  });
  if (res.status === 204) return new NextResponse(null, { status: 204 });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
