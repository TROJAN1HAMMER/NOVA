import { useAuth } from "./useAuth";

/**
 * Reads the fully-resolved permission set the backend already computed for
 * the current user's role (`User.permissions`, from
 * backend/app/auth/permissions.py's ROLE_PERMISSIONS) — components gate
 * actions off this instead of hardcoding/duplicating the role->permission
 * matrix in TypeScript.
 */
export function usePermissions() {
  const { user } = useAuth();
  const permissions = user?.permissions ?? [];

  const hasPermission = (permission: string) =>
    user?.role === "admin" || permissions.includes("*") || permissions.includes(permission);

  return {
    hasPermission,
    permissions,
    role: user?.role,
    roleDisplayName: user?.role_display_name,
  };
}

