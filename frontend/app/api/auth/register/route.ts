import { NextRequest } from "next/server";
import { proxyToApi } from "@/lib/proxy";

export async function POST(request: NextRequest) {
  const body = await request.json();

  return proxyToApi(request, "/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
