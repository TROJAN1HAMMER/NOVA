import type { UserRole } from "../types/api";

// NOVA AEKOF platform roles — maps to UserRole in types/api.ts
export const ROLE_DISPLAY_NAMES: Record<UserRole, string> = {
  admin: "Platform Administrator",
  security_engineer: "AI Systems Engineer",
  developer: "Knowledge Analyst",
  auditor: "Executive / Auditor",
  read_only: "Read Only",
};

export const ALL_ROLES: UserRole[] = [
  "admin",
  "security_engineer",
  "developer",
  "auditor",
  "read_only",
];

export const ROUTE_ROLES = {
  assistant: ["admin", "security_engineer", "developer", "auditor", "read_only"],
  "source-studio": ["admin", "security_engineer", "developer"],
  knowledge: ["admin", "security_engineer", "developer", "auditor", "read_only"],
  "graph-explorer": ["admin", "security_engineer", "developer", "auditor", "read_only"],
  memory: ["admin", "security_engineer", "developer", "auditor", "read_only"],
  "knowledge-evolution": ["admin", "security_engineer", "developer"],
  "rag-operations": ["admin", "security_engineer", "auditor"],
  benchmarks: ["admin", "security_engineer", "auditor", "read_only"],
  executive: ["admin", "security_engineer", "auditor", "read_only"],
  "my-activity": ["admin", "security_engineer", "developer", "auditor", "read_only"],
  "admin/users": ["admin"],
  scans: ["admin", "security_engineer", "developer", "auditor", "read_only"],
} as const satisfies Record<string, UserRole[]>;

export type RouteKey = keyof typeof ROUTE_ROLES;

export const DEFAULT_ROUTE_FOR_ROLE: Record<UserRole, string> = {
  admin: "/assistant",
  security_engineer: "/assistant",
  developer: "/assistant",
  auditor: "/executive",
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
