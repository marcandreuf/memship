import { NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8003";

// No cookie forwarded: the branding subset is unauthenticated by design, and
// the shell asks for it before it knows who is looking.
export async function GET() {
  const res = await fetch(`${API_BASE_URL}/api/v1/settings/branding`, {
    cache: "no-store",
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
