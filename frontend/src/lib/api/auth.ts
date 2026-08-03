import { apiClient, tokenStorage } from "./client";
import type { TokenResponse, User } from "../../types/api";

export const authApi = {
  login: async (email: string, password: string): Promise<TokenResponse> => {
    const body = new URLSearchParams();
    body.set("username", email);
    body.set("password", password);
    const response = await apiClient.post<TokenResponse>("/auth/login", body, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    tokenStorage.setTokens(response.data);
    return response.data;
  },

  register: async (email: string, password: string, fullName?: string): Promise<User> => {
    const response = await apiClient.post<User>("/auth/register", {
      email,
      password,
      full_name: fullName || undefined,
    });
    return response.data;
  },

  me: async (): Promise<User> => {
    const response = await apiClient.get<User>("/auth/me");
    return response.data;
  },

  logout: () => {
    tokenStorage.clear();
  },
};
