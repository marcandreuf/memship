import { NextRequest } from "next/server";
import { proxyToApi } from "@/lib/proxy";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.text();
  return proxyToApi(request, `/registrations/${id}/refund-returned`, {
    method: "POST",
    ...(body ? { body, headers: { "Content-Type": "application/json" } } : {}),
  });
}
