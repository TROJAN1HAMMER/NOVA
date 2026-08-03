import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ragOperationsApi } from "../lib/api/ragOperations";

export function useSearchAnalytics(feature?: string) {
  return useQuery({
    queryKey: ["rag-search-analytics", feature ?? "all"],
    queryFn: () => ragOperationsApi.getSearchAnalytics(feature),
  });
}

export function useFeedbackSummary(feature?: string) {
  return useQuery({
    queryKey: ["rag-feedback-summary", feature ?? "all"],
    queryFn: () => ragOperationsApi.getFeedbackSummary(feature),
  });
}

export function useRunBenchmark() {
  return useMutation({
    mutationFn: () => ragOperationsApi.runBenchmark(),
  });
}

export function useSubmitFeedback() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { feature: string; reference_id: string; rating: 1 | -1; comment?: string }) =>
      ragOperationsApi.submitFeedback(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rag-feedback-summary"] });
    },
  });
}
