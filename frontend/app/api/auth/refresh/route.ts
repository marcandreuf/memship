import { NextRequest } from "next/server";
import { proxyToApi } from "@/lib/proxy";

export async function POST(request: NextRequest) {
  // The whole point of this route is that the renewed cookie reaches the
  // browser; `proxyToApi` forwards `set-cookie` for every route.
  return proxyToApi(request, "/auth/refresh", { method: "POST" });
}
