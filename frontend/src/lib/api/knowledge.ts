import { apiClient } from "./client";
import type { KnowledgeDocumentListResponse, KnowledgeDocument, KnowledgeSearchResponse } from "../../types/api";

export interface KnowledgeDocumentListParams {
  document_type?: string;
  status?: string;
  tag?: string;
  limit?: number;
  offset?: number;
}

export interface KnowledgeUploadPayload {
  file: File;
  version?: string;
  author?: string;
  tags?: string; // comma-separated, matches backend's Form field
}

export interface KnowledgeSearchPayload {
  query: string;
  top_k?: number;
  document_type?: string;
  tag?: string;
}

export const knowledgeApi = {
  listDocuments: async (params: KnowledgeDocumentListParams = {}): Promise<KnowledgeDocumentListResponse> => {
    const response = await apiClient.get<KnowledgeDocumentListResponse>("/knowledge/documents", { params });
    return response.data;
  },

  upload: async (payload: KnowledgeUploadPayload): Promise<KnowledgeDocument> => {
    const formData = new FormData();
    formData.append("file", payload.file);
    if (payload.version) formData.append("version", payload.version);
    if (payload.author) formData.append("author", payload.author);
    if (payload.tags) formData.append("tags", payload.tags);
    const response = await apiClient.post<KnowledgeDocument>("/knowledge/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
  },

  deleteDocument: async (documentId: string): Promise<void> => {
    await apiClient.delete(`/knowledge/document/${documentId}`);
  },

  search: async (payload: KnowledgeSearchPayload): Promise<KnowledgeSearchResponse> => {
    const response = await apiClient.post<KnowledgeSearchResponse>("/knowledge/search", payload);
    return response.data;
  },
};
