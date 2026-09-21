/**
 * The one place a Next.js API route decides which headers cross the proxy.
 *
 * Every browser request reaches FastAPI through a route under `app/api/`,
 * which rebuilds the request and the response. What it does not copy across
 * is lost, and each route used to decide that on its own — so the caller's
 * address never reached the API: the login throttle keyed every member to
 * the frontend container and twenty-one bad passwords from anywhere locked
 * the whole club out (#241).
 *
 * `X-Forwarded-For` is forwarded verbatim and the proxy does not append its
 * own hop. Caddy already appended the browser's address before handing the
 * request to Next.js, and `/api/v1/*` reaches the API from Caddy directly
 * with that same header — so the API sees one chain whichever path a request
 * took, and `TRUSTED_PROXY_HOPS` counts the proxies in front of the
 * deployment, not the frontend behind them.
 */

import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8003";

/** Headers from the browser's request that the API needs to see. */
const REQUEST_HEADERS = ["cookie", "x-forwarded-for"] as const;

/** Headers from the API's response that the browser needs to see. */
const RESPONSE_HEADERS = ["set-cookie"] as const;

/**
 * The headers for a call to the API on behalf of `request`, plus `extra`.
 */
export function apiRequestHeaders(
  request: NextRequest,
  extra: Record<string, string> = {}
): Record<string, string> {
  const headers: Record<string, string> = {};
  for (const name of REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers[name] = value;
  }
  return { ...headers, ...extra };
}

/**
 * Build the browser's response from the API's: its status, its JSON body, and
 * the headers the browser has a use for.
 */
export async function apiResponse(res: Response): Promise<NextResponse> {
  const data = await res.json().catch(() => null);
  const response =
    data === null
      ? new NextResponse(null, { status: res.status })
      : NextResponse.json(data, { status: res.status });
  for (const name of RESPONSE_HEADERS) {
    const value = res.headers.get(name);
    if (value) response.headers.set(name, value);
  }
  return response;
}

/**
 * Forward `request` to the API at `path` (relative to `/api/v1`) and hand the
 * answer back. `init` is the fetch init for the API call; its `headers` are
 * merged over the forwarded ones.
 */
export async function proxyToApi(
  request: NextRequest,
  path: string,
  init: RequestInit & { headers?: Record<string, string> } = {}
): Promise<NextResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1${path}`, {
    ...init,
    headers: apiRequestHeaders(request, init.headers),
  });
  return apiResponse(res);
}
