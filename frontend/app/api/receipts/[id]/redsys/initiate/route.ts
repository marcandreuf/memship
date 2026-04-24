import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8003";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const cookie = request.headers.get("cookie") || "";
  const body = await request.text();
  const res = await fetch(
    `${API_BASE_URL}/api/v1/receipts/${id}/redsys/initiate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Cookie: cookie },
      body: body || "{}",
    }
  );
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
