import { NextRequest } from "next/server";
import { proxyToApi } from "@/lib/proxy";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyToApi(request, `/bookings/${id}/confirm-without-payment`, { method: "POST" });
}
