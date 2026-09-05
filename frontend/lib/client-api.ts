/**
 * Client-side API client — calls Next.js API routes (which proxy to backend).
 * Used in React Client Components via hooks.
 */

type UnauthorizedHandler = () => void;

let unauthorizedHandler: UnauthorizedHandler | null = null;
let handlingUnauthorized = false;

/**
 * Register what happens when a signed-in session turns out to be dead.
 *
 * Only the portal registers one (see SessionGuard), so a 401 on the login page
 * — a wrong password — stays an ordinary error the form renders itself.
 */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null) {
  unauthorizedHandler = handler;
  if (!handler) handlingUnauthorized = false;
}

/**
 * Endpoints that answer 401 as a normal outcome rather than as an expired
 * session. Bad credentials must not read as "you were signed out".
 */
const EXPECTED_401_ENDPOINTS = ["/auth/login", "/auth/register"];

function isSessionExpiry(endpoint: string, status: number): boolean {
  if (status !== 401) return false;
  return !EXPECTED_401_ENDPOINTS.some((path) => endpoint.startsWith(path));
}

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

    // A page mid-session fires several requests at once, so they all fail
    // together — send the user to the login screen once, not once per request.
    if (isSessionExpiry(endpoint, res.status) && !handlingUnauthorized) {
      handlingUnauthorized = true;
      unauthorizedHandler?.();
    }

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
