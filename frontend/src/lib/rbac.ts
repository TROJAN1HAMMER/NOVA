import type { UserRole } from "../types/api";

// NOVA AEKOF platform roles — maps to UserRole in types/api.ts
export const ROLE_DISPLAY_NAMES: Record<UserRole, string> = {
  admin: "Platform Administrator",
  analyst: "AI Systems Analyst",
  developer: "Knowledge Engineer",
  contributor: "Knowledge Contributor",
  read_only: "Observer",
};

export const ALL_ROLES: UserRole[] = ["admin", "analyst", "developer", "contributor", "read_only"];

export const ROUTE_ROLES = {
  assistant: ["admin", "analyst", "developer", "contributor", "read_only"],
  "source-studio": ["admin", "analyst", "developer", "contributor"],
  knowledge: ["admin", "analyst", "developer", "contributor", "read_only"],
  "graph-explorer": ["admin", "analyst", "developer", "read_only"],
  memory: ["admin", "analyst", "developer", "read_only"],
  "knowledge-evolution": ["admin", "analyst", "developer"],
  "rag-operations": ["admin", "analyst"],
  benchmarks: ["admin", "analyst", "read_only"],
  executive: ["admin", "analyst", "read_only"],
  "my-activity": ["admin", "analyst", "developer", "contributor"],
  "admin/users": ["admin"],
  scans: ["admin", "analyst", "developer", "contributor", "read_only"],
} as const satisfies Record<string, UserRole[]>;

export type RouteKey = keyof typeof ROUTE_ROLES;

export const DEFAULT_ROUTE_FOR_ROLE: Record<UserRole, string> = {
  admin: "/assistant",
  analyst: "/assistant",
  developer: "/assistant",
  contributor: "/source-studio",
  read_only: "/assistant",
};

export function canAccessRoute(role: UserRole | undefined | null, routeKey: RouteKey): boolean {
  if (!role) return false;
  return (ROUTE_ROLES[routeKey] as readonly UserRole[]).includes(role);
}

export function defaultRouteForRole(role: UserRole | undefined | null): string {
  if (!role) return "/login";
  return DEFAULT_ROUTE_FOR_ROLE[role];
}
