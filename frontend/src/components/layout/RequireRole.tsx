import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { canAccessRoute, defaultRouteForRole, type RouteKey } from "../../lib/rbac";

/**
 * Sibling to ProtectedRoute — that one only checks "is anyone logged in
 * at all"; this one checks "can THIS role see THIS page." Nested inside
 * ProtectedRoute (which already handles the loading/unauthenticated
 * cases), so by the time this renders there's always a `user` present.
 *
 * This is a UX nicety, not the security boundary — every one of these
 * routes' underlying API calls is independently permission-checked
 * server-side (require_permission(...) dependencies), so a role blocked
 * here couldn't do anything harmful even if this check were skipped. The
 * point is purely to avoid showing a broken/empty page for a route a
 * role's own nav doesn't even link to.
 */
export function RequireRole({ routeKey, children }: { routeKey: RouteKey; children: ReactNode }) {
  const { user } = useAuth();
  if (!user) return null;
  if (!canAccessRoute(user.role, routeKey)) {
    return <Navigate to={defaultRouteForRole(user.role)} replace />;
  }
  return <>{children}</>;
}
