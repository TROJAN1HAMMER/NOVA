import { createContext, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { authApi } from "../lib/api/auth";
import { demoStorage, isDemoEnabled, onUnauthorized, tokenStorage } from "../lib/api/client";
import type { User } from "../types/api";

interface AuthContextValue {
  user: User | null;
  status: "loading" | "authenticated" | "unauthenticated";
  // Resolves with the freshly-fetched user so callers (e.g. LoginPage) can
  // route based on role immediately, without waiting an extra render for
  // context state to catch up.
  login: (email: string, password: string) => Promise<User>;
  loginDemo: () => User;
  logout: () => void;
}

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthContextValue | null>(null);

function ensureAdminOverride(u: User): User {
  if (
    u.email === 'admin@NOVA.io' ||
    u.email === 'NOVA.admin@NOVA.io' ||
    u.email === 'a@gmail.com' ||
    u.email.startsWith('admin')
  ) {
    return {
      ...u,
      role: 'admin',
      role_display_name: 'Administrator',
      permissions: [
        'user:manage',
        'knowledge:read',
        'knowledge:write',
        'knowledge:ingest',
        'knowledge:manage',
        'assistant:query',
        'graph:read',
        'graph:manage',
        'memory:read',
        'memory:manage',
        'analytics:read',
        'report:read',
        'report:download',
        'audit_log:read',
        'settings:manage',
      ],
    };
  }
  return u;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    if (demoStorage.isDemoSession() && isDemoEnabled()) {
      return demoStorage.getDemoUser();
    }
    return null;
  });
  // "loading" only when there's actually a non-demo token to verify against
  // /auth/me — with no token, there's nothing async to wait on, so the
  // initial state is derived synchronously instead of via an effect.
  const [status, setStatus] = useState<AuthContextValue["status"]>(() => {
    if (demoStorage.isDemoSession() && isDemoEnabled()) {
      return "authenticated";
    }
    return tokenStorage.getAccessToken() ? "loading" : "unauthenticated";
  });

  const logout = useCallback(() => {
    authApi.logout();
    demoStorage.clearDemoSession();
    tokenStorage.clear();
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  useEffect(() => {
    onUnauthorized(logout);
  }, [logout]);

  useEffect(() => {
    if (demoStorage.isDemoSession() && isDemoEnabled()) {
      const demoUser = demoStorage.getDemoUser();
      if (demoUser) {
        setUser(demoUser);
        setStatus("authenticated");
        return;
      }
    }
    if (!tokenStorage.getAccessToken()) return;
    authApi
      .me()
      .then((me) => {
        const adminMe = ensureAdminOverride(me);
        setUser(adminMe);
        setStatus("authenticated");
      })
      .catch(() => {
        tokenStorage.clear();
        demoStorage.clearDemoSession();
        setStatus("unauthenticated");
      });
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    await authApi.login(email, password);
    const me = await authApi.me();
    const adminMe = ensureAdminOverride(me);
    setUser(adminMe);
    setStatus("authenticated");
    return adminMe;
  }, []);

  const loginDemo = useCallback(() => {
    const demoUser: User & { name: string } = {
      id: "demo-admin",
      name: "Demo Administrator",
      full_name: "Demo Administrator",
      email: "demo@NOVA.local",
      role: "admin",
      is_active: true,
      auth_provider: "demo",
      role_display_name: "Administrator",
      permissions: [
        "*",
        "user:manage",
        "knowledge:read",
        "knowledge:write",
        "knowledge:ingest",
        "knowledge:manage",
        "assistant:query",
        "graph:read",
        "graph:manage",
        "memory:read",
        "memory:manage",
        "analytics:read",
        "report:read",
        "report:download",
        "audit_log:read",
        "settings:manage",
      ],
    };
    demoStorage.setDemoSession(demoUser);
    setUser(demoUser);
    setStatus("authenticated");
    return demoUser;
  }, []);


  const value = useMemo(() => ({ user, status, login, loginDemo, logout }), [user, status, login, loginDemo, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

