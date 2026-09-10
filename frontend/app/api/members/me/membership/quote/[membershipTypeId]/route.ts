import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8003";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ membershipTypeId: string }> }
) {
  const { membershipTypeId } = await params;
  const cookie = request.headers.get("cookie") || "";
  const res = await fetch(
    `${API_BASE_URL}/api/v1/members/me/membership/quote/${membershipTypeId}`,
    { headers: { Cookie: cookie } }
  );
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
