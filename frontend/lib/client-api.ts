/**
 * Client-side API client — calls Next.js API routes (which proxy to backend).
 * Used in React Client Components via hooks.
 */

export async function apiClient<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`/api${endpoint}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
    ...options,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ClientApiError(res.status, error.detail || res.statusText);
  }

  return res.json();
}

export class ClientApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ClientApiError";
  }
}
