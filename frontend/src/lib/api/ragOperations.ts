import { apiClient } from "./client";
import type { BenchmarkResult, FeedbackSummary, SearchAnalyticsSummary } from "../../types/api";

export const ragOperationsApi = {
  runBenchmark: async (): Promise<BenchmarkResult> => {
    const response = await apiClient.post<BenchmarkResult>("/rag-operations/benchmark");
    return response.data;
  },

  getSearchAnalytics: async (feature?: string): Promise<SearchAnalyticsSummary> => {
    const response = await apiClient.get<SearchAnalyticsSummary>("/rag-operations/search-analytics", {
      params: feature ? { feature } : undefined,
    });
    return response.data;
  },

  getFeedbackSummary: async (feature?: string): Promise<FeedbackSummary> => {
    const response = await apiClient.get<FeedbackSummary>("/feedback/summary", {
      params: feature ? { feature } : undefined,
    });
    return response.data;
  },

  submitFeedback: async (payload: {
    feature: string;
    reference_id: string;
    rating: 1 | -1;
    comment?: string;
  }): Promise<void> => {
    await apiClient.post("/feedback", payload);
  },
};
