/**
 * Server-side API client — reads auth cookie from request headers.
 * Used in Next.js Server Components and API routes.
 */

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:8003";

export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit & { cookie?: string } = {}
): Promise<T> {
  const { cookie, ...fetchOptions } = options;

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(cookie ? { Cookie: cookie } : {}),
    ...((fetchOptions.headers as Record<string, string>) || {}),
  };

  const res = await fetch(`${API_BASE_URL}/api/v1${endpoint}`, {
    ...fetchOptions,
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, error.detail || res.statusText);
  }

  return res.json();
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}
