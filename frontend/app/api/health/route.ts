import { NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8003";

export async function GET() {
  const res = await fetch(`${API_BASE_URL}/api/v1/health`, {
    cache: "no-store",
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
