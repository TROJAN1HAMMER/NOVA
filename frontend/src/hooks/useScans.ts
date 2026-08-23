import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { scanApi } from "../lib/api/scan";

export function useScanJobs(params?: { status?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: ["scans", params],
    queryFn: () => scanApi.listScans(params),
    refetchInterval: 3000, // Poll every 3 seconds
  });
}

export function useScanStatus(scanJobId: string) {
  return useQuery({
    queryKey: ["scans", scanJobId],
    queryFn: () => scanApi.getScanStatus(scanJobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "completed" || status === "failed" || status === "cancelled") {
        return false;
      }
      return 3000;
    },
  });
}

export function useScanFindings(scanJobId: string) {
  return useQuery({
    queryKey: ["scans", scanJobId, "findings"],
    queryFn: () => scanApi.getScanFindings(scanJobId),
  });
}

export function useScanCompliance(scanJobId: string) {
  return useQuery({
    queryKey: ["scans", scanJobId, "compliance"],
    queryFn: () => scanApi.getScanCompliance(scanJobId),
  });
}

export function useSubmitScan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: scanApi.submitRepository,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scans"] });
    },
  });
}
