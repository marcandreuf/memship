"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "@/lib/i18n/routing";
import {
  getMe,
  login,
  logout,
  register,
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
  });

  const loginMutation = useMutation({
    mutationFn: (data: LoginData) => login(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: AUTH_QUERY_KEY });
      router.push("/dashboard");
    },
  });

  const registerMutation = useMutation({
    mutationFn: (data: RegisterData) => register(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: AUTH_QUERY_KEY });
      router.push("/dashboard");
    },
  });

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      queryClient.clear();
      router.push("/login");
    },
  });

  return {
    user: user ?? null,
    isLoading,
    isAuthenticated: !!user,
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
