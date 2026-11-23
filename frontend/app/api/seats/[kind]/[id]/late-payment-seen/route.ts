import { NextRequest } from "next/server";
import { proxyToApi } from "@/lib/proxy";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ kind: string; id: string }> }
) {
  const { kind, id } = await params;
  const body = await request.text();
  return proxyToApi(request, `/seats/${kind}/${id}/late-payment-seen`, {
    method: "POST",
    ...(body ? { body, headers: { "Content-Type": "application/json" } } : {}),
  });
}
