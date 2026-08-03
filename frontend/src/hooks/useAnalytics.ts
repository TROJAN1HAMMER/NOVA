import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "../lib/api/analytics";
import { queryKeys } from "../lib/queryClient";

export function useMyActivity() {
  return useQuery({
    queryKey: queryKeys.myActivity(),
    queryFn: () => analyticsApi.myActivity(),
  });
}

export function useTeamActivity(enabled = true) {
  return useQuery({
    queryKey: queryKeys.teamActivity(),
    queryFn: () => analyticsApi.teamActivity(),
    // Gated by the caller (route/nav already restrict this to
    // security_engineer/admin) — `enabled` lets a page avoid firing the
    // request at all for a role that would just get a 403 back.
    enabled,
  });
}
