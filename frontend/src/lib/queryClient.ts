import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

// Central query key registry — all hooks reference these so cache
// invalidation and WebSocket writers always target the correct key shape.
export const queryKeys = {
  currentUser: () => ["current-user"] as const,

  // Knowledge Base
  knowledgeDocuments: (params?: unknown) => ["knowledge-documents", params ?? {}] as const,
  knowledgeSearch: (query?: string) => ["knowledge-search", query ?? ""] as const,
  knowledgeJob: (jobId: string) => ["knowledge-job", jobId] as const,
  knowledgeJobs: (filters?: unknown) => ["knowledge-jobs", filters ?? {}] as const,

  // Graph & Memory
  graphSnapshot: () => ["graph-snapshot"] as const,
  memoryState: () => ["memory-state"] as const,

  // Analytics
  myActivity: () => ["my-activity"] as const,
  teamActivity: () => ["team-activity"] as const,

  // Executive Intelligence
  executiveIntelligence: () => ["executive-intelligence"] as const,

  // RAG / Benchmark
  ragBenchmark: () => ["rag-benchmark"] as const,
  searchAnalytics: () => ["search-analytics"] as const,
  feedbackSummary: () => ["feedback-summary"] as const,

  // FAQ & Knowledge Evolution
  faqEntries: (params?: unknown) => ["faq-entries", params ?? {}] as const,
  gapClusters: (params?: unknown) => ["gap-clusters", params ?? {}] as const,

  // Reports
  reportStatus: (operationId: string) => ["report-status", operationId] as const,

  // Admin
  adminUsers: (params?: unknown) => ["admin-users", params ?? {}] as const,
  auditLog: (params?: unknown) => ["audit-log", params ?? {}] as const,
  systemSettings: () => ["system-settings"] as const,
};
