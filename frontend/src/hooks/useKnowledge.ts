import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  knowledgeApi,
  type KnowledgeDocumentListParams,
  type KnowledgeSearchPayload,
  type KnowledgeUploadPayload,
} from "../lib/api/knowledge";
import { queryKeys } from "../lib/queryClient";

const IN_PROGRESS_STATUSES = new Set(["pending", "processing"]);

export function useKnowledgeDocuments(params: KnowledgeDocumentListParams = {}) {
  return useQuery({
    queryKey: queryKeys.knowledgeDocuments(params),
    queryFn: () => knowledgeApi.listDocuments(params),
    // A document goes pending -> processing -> indexed|failed on its own
    // (see app/tasks/knowledge_tasks.py) — poll while any row is still
    // mid-flight so the status column advances without a manual refresh.
    refetchInterval: (query) => {
      const documents = query.state.data?.documents ?? [];
      return documents.some((doc) => IN_PROGRESS_STATUSES.has(doc.status)) ? 3_000 : false;
    },
  });
}

export function useUploadKnowledgeDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: KnowledgeUploadPayload) => knowledgeApi.upload(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-documents"] });
    },
  });
}

export function useDeleteKnowledgeDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: string) => knowledgeApi.deleteDocument(documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-documents"] });
    },
  });
}

// A search (mutation, not a query): each submission is a distinct
// user-triggered action with its own result set, not a cacheable resource
// keyed by a stable identifier — the same shape as any "run this action
// now" request in this codebase.
export function useSearchKnowledge() {
  return useMutation({
    mutationFn: (payload: KnowledgeSearchPayload) => knowledgeApi.search(payload),
  });
}
