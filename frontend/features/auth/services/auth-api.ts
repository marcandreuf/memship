import { apiClient, ClientApiError } from "@/lib/client-api";

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

export async function register(data: RegisterData): Promise<User> {
  return apiClient("/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
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
