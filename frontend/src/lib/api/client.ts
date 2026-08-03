import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import type { TokenResponse, User } from "../../types/api";

export const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

const ACCESS_TOKEN_KEY = "NOVA.access_token";
const REFRESH_TOKEN_KEY = "NOVA.refresh_token";
const DEMO_SESSION_KEY = "NOVA.demo_session";
const DEMO_USER_KEY = "NOVA.demo_user";

export const isDemoEnabled = () => true;

export const demoStorage = {
  isDemoSession: () => localStorage.getItem(DEMO_SESSION_KEY) === "true",
  getDemoUser: (): User | null => {
    const raw = localStorage.getItem(DEMO_USER_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  },
  setDemoSession: (user: User) => {
    localStorage.setItem(DEMO_SESSION_KEY, "true");
    localStorage.setItem(DEMO_USER_KEY, JSON.stringify(user));
    localStorage.setItem(ACCESS_TOKEN_KEY, "demo-admin-bearer-token");
    localStorage.setItem(REFRESH_TOKEN_KEY, "demo-admin-refresh-token");
  },
  clearDemoSession: () => {
    localStorage.removeItem(DEMO_SESSION_KEY);
    localStorage.removeItem(DEMO_USER_KEY);
  },
};

export const tokenStorage = {
  getAccessToken: () => localStorage.getItem(ACCESS_TOKEN_KEY),
  getRefreshToken: () => localStorage.getItem(REFRESH_TOKEN_KEY),
  setTokens: (tokens: TokenResponse) => {
    localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
  },
  clear: () => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    demoStorage.clearDemoSession();
  },
};

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.request.use((config) => {
  const token = tokenStorage.getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

type UnauthorizedListener = () => void;
let unauthorizedListener: UnauthorizedListener | null = null;
export function onUnauthorized(listener: UnauthorizedListener) {
  unauthorizedListener = listener;
}

let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = tokenStorage.getRefreshToken();
  if (!refreshToken) return null;

  try {
    const response = await axios.post<TokenResponse>(`${API_BASE_URL}/auth/refresh`, { refresh_token: refreshToken });
    tokenStorage.setTokens(response.data);
    return response.data.access_token;
  } catch {
    return null;
  }
}

interface RetriableConfig extends InternalAxiosRequestConfig {
  _retried?: boolean;
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetriableConfig | undefined;
    const isAuthEndpoint = config?.url?.includes("/auth/login") || config?.url?.includes("/auth/refresh");

    if (error.response?.status !== 401 || !config || config._retried || isAuthEndpoint) {
      throw error;
    }
    config._retried = true;

    if (demoStorage.isDemoSession()) {
      throw error;
    }

    if (!refreshPromise) {
      refreshPromise = refreshAccessToken().finally(() => {
        refreshPromise = null;
      });
    }
    const newAccessToken = await refreshPromise;

    if (!newAccessToken) {
      tokenStorage.clear();
      unauthorizedListener?.();
      throw error;
    }

    config.headers.Authorization = `Bearer ${newAccessToken}`;
    return apiClient(config);
  },
);
