import { apiFetch } from "@/lib/api";

export interface OwnerUser {
  id: string;
  email: string;
  full_name: string;
}

export interface AuthStatus {
  initialized: boolean;
  authenticated: boolean;
  owner_email_configured: boolean;
  user: OwnerUser | null;
}

export interface AuthResponse {
  status: string;
  token?: string;
  message?: string;
  user?: OwnerUser;
}

export const authApi = {
  status: () => apiFetch<AuthStatus>("/api/auth/status"),

  bootstrap: (data: { email: string; password: string; full_name?: string; bootstrap_token?: string }) =>
    apiFetch<AuthResponse>("/api/auth/bootstrap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  login: (data: { email: string; password: string }) =>
    apiFetch<AuthResponse>("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),

  logout: () =>
    apiFetch<{ status: string; message: string }>("/api/auth/logout", {
      method: "POST",
    }),

  me: () => apiFetch<OwnerUser & { is_active: boolean; created_at: string; last_login_at: string | null }>("/api/auth/me"),

  changePassword: (data: { current_password: string; new_password: string }) =>
    apiFetch<{ status: string; message: string }>("/api/auth/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
};
