import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8003";

export async function POST(request: NextRequest) {
  const cookie = request.headers.get("cookie") || "";

  const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { Cookie: cookie },
  });

  const data = await res.json();
  const response = NextResponse.json(data, { status: res.status });

  // The whole point of this route: the renewed cookie has to reach the browser.
  // Every other proxy here returns NextResponse.json alone and drops the
  // backend's response headers, which is why the session could not slide.
  const setCookie = res.headers.get("set-cookie");
  if (setCookie) {
    response.headers.set("set-cookie", setCookie);
  }

  return response;
}
