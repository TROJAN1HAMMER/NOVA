import { apiClient } from "./client";
import type { MyKnowledgeActivitySummary, TeamKnowledgeActivitySummary } from "../../types/api";

export const analyticsApi = {
  myActivity: async (): Promise<MyKnowledgeActivitySummary> => {
    const response = await apiClient.get<MyKnowledgeActivitySummary>("/analytics/my-activity");
    return response.data;
  },

  // Server-gated by "team_analytics:read" (analyst/admin only) —
  // callers should also route/nav-gate this so a role lacking it never
  // fires the request in the first place; a 403 here is a defense-in-depth
  // backstop, not the primary UX.
  teamActivity: async (): Promise<TeamKnowledgeActivitySummary> => {
    const response = await apiClient.get<TeamKnowledgeActivitySummary>("/analytics/team-activity");
    return response.data;
  },
};
