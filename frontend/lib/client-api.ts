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
    throw new ClientApiError(res.status, error.detail ?? res.statusText);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export type ValidationErrorDetail = {
  loc: (string | number)[];
  msg: string;
  type: string;
};

export class ClientApiError extends Error {
  public detail: string | ValidationErrorDetail[];
  constructor(public status: number, detail: string | ValidationErrorDetail[]) {
    super(typeof detail === "string" ? detail : "Validation error");
    this.name = "ClientApiError";
    this.detail = detail;
  }
}
