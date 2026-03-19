import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8003";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const cookie = request.headers.get("cookie") || "";
  const res = await fetch(`${API_BASE_URL}/api/v1/registrations/${id}/attachments`, {
    headers: { Cookie: cookie },
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const cookie = request.headers.get("cookie") || "";
  const searchParams = request.nextUrl.searchParams.toString();
  const formData = await request.formData();
  const url = `${API_BASE_URL}/api/v1/registrations/${id}/attachments${searchParams ? `?${searchParams}` : ""}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { Cookie: cookie },
    body: formData,
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
