import { apiClient } from "./client";
import type { MyActivitySummary, TeamActivitySummary } from "../../types/api";

export const analyticsApi = {
  myActivity: async (): Promise<MyActivitySummary> => {
    const response = await apiClient.get<MyActivitySummary>("/analytics/my-activity");
    return response.data;
  },

  // Server-gated by "team_analytics:read" (security_engineer/auditor/admin only) —
  // callers should also route/nav-gate this so a role lacking it never
  // fires the request in the first place; a 403 here is a defense-in-depth
  // backstop, not the primary UX.
  teamActivity: async (): Promise<TeamActivitySummary> => {
    const response = await apiClient.get<TeamActivitySummary>("/analytics/team-activity");
    return response.data;
  },
};
