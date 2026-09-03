"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "@/lib/i18n/routing";
import {
  ClientApiError,
  getMe,
  login,
  logout,
  register,
  resendVerification,
  verifyEmail,
  type LoginData,
  type RegisterData,
  type User,
} from "../services/auth-api";

const AUTH_QUERY_KEY = ["auth", "me"];

export function useAuth() {
  const queryClient = useQueryClient();
  const router = useRouter();

  const {
    data: user,
    isLoading,
    error,
  } = useQuery<User>({
    queryKey: AUTH_QUERY_KEY,
    queryFn: getMe,
    retry: false,
    staleTime: 5 * 60 * 1000,
    // The server resolves permissions per request, so a revoked role takes
    // effect there immediately. Without refetching, this cached copy would keep
    // rendering nav the user can no longer use until a full reload.
    refetchOnWindowFocus: true,
  });

  const loginMutation = useMutation({
    mutationFn: (data: LoginData) => login(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: AUTH_QUERY_KEY });
      router.push("/dashboard");
    },
  });

  // No redirect on success: registration no longer opens a session. The form
  // shows a "confirm your email / awaiting approval" panel from the result.
  const registerMutation = useMutation({
    mutationFn: (data: RegisterData) => register(data),
  });

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      queryClient.clear();
      router.push("/login");
    },
  });

  // React Query keeps the last successful data when a refetch fails, so an
  // expired session left `user` populated and every consumer believing the
  // visitor was still signed in — the portal kept rendering a shell whose every
  // request 401ed, until a manual reload finally emptied the cache.
  const sessionExpired =
    error instanceof ClientApiError && error.status === 401;

  return {
    user: sessionExpired ? null : (user ?? null),
    isLoading,
    isAuthenticated: !!user && !sessionExpired,
    error,
    login: loginMutation.mutateAsync,
    loginError: loginMutation.error,
    isLoggingIn: loginMutation.isPending,
    register: registerMutation.mutateAsync,
    registerError: registerMutation.error,
    isRegistering: registerMutation.isPending,
    logout: logoutMutation.mutateAsync,
  };
}

export function useVerifyEmail() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (token: string) => verifyEmail(token),
    onSuccess: () => {
      // A signed-in pending member sees their banner update immediately.
      queryClient.invalidateQueries({ queryKey: AUTH_QUERY_KEY });
    },
  });
}

export function useResendVerification() {
  return useMutation({
    mutationFn: (email: string) => resendVerification(email),
  });
}
