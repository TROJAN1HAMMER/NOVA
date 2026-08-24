import { apiClient } from "./client";

export interface FAQRuleItem {
  id: string;
  keyword: string;
  response: string;
  is_active: boolean;
  is_draft: boolean;
}

export async function fetchFaqRules(): Promise<FAQRuleItem[]> {
  const { data } = await apiClient.get<FAQRuleItem[]>("/faq");
  return data;
}

export async function createFaqRule(payload: { keyword: string; response: string }): Promise<FAQRuleItem> {
  const { data } = await apiClient.post<FAQRuleItem>("/faq", payload);
  return data;
}

export async function deleteFaqRule(ruleId: string): Promise<void> {
  await apiClient.delete(`/faq/${ruleId}`);
}

export async function fetchGapInbox(): Promise<FAQRuleItem[]> {
  const { data } = await apiClient.get<FAQRuleItem[]>("/faq/gap-inbox");
  return data;
}

export async function promoteGapRule(ruleId: string): Promise<FAQRuleItem> {
  const { data } = await apiClient.post<FAQRuleItem>(`/faq/gap-inbox/${ruleId}/promote`);
  return data;
}

export async function fetchKnowledgeEvolutionMetrics() {
  const { data } = await apiClient.get<{
    total_queries: number;
    failure_refusal_rate: number | null;
    stage_0_match_ratio: number | null;
    pending_gap_candidates_count: number;
    active_faq_count: number;
  }>("/faq/evolution-metrics");
  return data;
}
