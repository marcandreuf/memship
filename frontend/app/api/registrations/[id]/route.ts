import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8003";

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const cookie = request.headers.get("cookie") || "";
  let body: string | undefined;
  try {
    const json = await request.json();
    body = JSON.stringify(json);
  } catch {
    // No body is fine for DELETE
  }
  const res = await fetch(`${API_BASE_URL}/api/v1/registrations/${id}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json", Cookie: cookie },
    ...(body ? { body } : {}),
  });
  if (res.status === 204) return new NextResponse(null, { status: 204 });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
