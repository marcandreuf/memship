import { apiClient, ClientApiError } from "@/lib/client-api";

export type MemberStatus =
  | "pending"
  | "active"
  | "suspended"
  | "cancelled"
  | "expired";

export interface User {
  id: number;
  email: string;
  role: "super_admin" | "admin" | "member";
  is_active: boolean;
  person_id: number;
  first_name: string;
  last_name: string;
  member_id: number | null;
  member_number: string | null;
  gender: string | null;
  email_verified: boolean;
  /** null for staff accounts that have no member record */
  member_status: MemberStatus | null;
}

export interface LoginData {
  email: string;
  password: string;
}

export interface RegisterData {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
}

export async function login(data: LoginData): Promise<{ message: string }> {
  return apiClient("/auth/login", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/** Registration does not open a session — it reports what happens next. */
export interface RegisterResult {
  message: string;
  email: string;
  member_status: MemberStatus;
  requires_approval: boolean;
  email_verified: boolean;
  /** Only returned when no email transport is configured (dev setups). */
  verification_token: string | null;
}

export async function register(data: RegisterData): Promise<RegisterResult> {
  return apiClient("/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function verifyEmail(token: string): Promise<{ message: string }> {
  return apiClient("/auth/verify-email", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export async function resendVerification(
  email: string
): Promise<{ message: string; verification_token: string | null }> {
  return apiClient("/auth/resend-verification", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function getMe(): Promise<User> {
  return apiClient("/auth/me");
}

export async function logout(): Promise<void> {
  await apiClient("/auth/logout", { method: "POST" });
}

export async function requestPasswordReset(
  email: string
): Promise<{ message: string; reset_token: string | null }> {
  return apiClient("/auth/password-reset-request", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function resetPassword(
  token: string,
  new_password: string
): Promise<{ message: string }> {
  return apiClient("/auth/password-reset", {
    method: "POST",
    body: JSON.stringify({ token, new_password }),
  });
}

export { ClientApiError };
