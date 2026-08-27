import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { settingsApi } from "../lib/api/settings";
import { queryKeys } from "../lib/queryClient";
import type { SystemSettings } from "../types/api";

export function useSystemSettings() {
  return useQuery({
    queryKey: queryKeys.systemSettings(),
    queryFn: () => settingsApi.getSettings(),
  });
}

export function useUpdateSystemSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (settings: Partial<SystemSettings>) => settingsApi.updateSettings(settings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.systemSettings() });
    },
  });
}

export function useResetSystemSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (keys?: string[]) => settingsApi.resetSettings(keys),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.systemSettings() });
    },
  });
}
