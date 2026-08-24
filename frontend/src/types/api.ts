// NOVA — API Type Definitions
// Mirrors backend Pydantic schemas. Field names/shapes must stay in sync
// with backend/app/schemas/*.py as the source of truth.

// ─────────────────────────────────────────────────────────────
// Auth & Users
// ─────────────────────────────────────────────────────────────

export type UserRole = "admin" | "security_engineer" | "developer" | "auditor" | "read_only";

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: UserRole;
  is_active: boolean;
  auth_provider: string;
  role_display_name: string;
  permissions: string[];
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// ─────────────────────────────────────────────────────────────
// Audit Log
// ─────────────────────────────────────────────────────────────

export interface AuditLogEntry {
  id: string;
  user_id: string | null;
  user_email: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  status: string;
  ip_address: string | null;
  user_agent: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditLogListResponse {
  total: number;
  limit: number;
  offset: number;
  entries: AuditLogEntry[];
}

// ─────────────────────────────────────────────────────────────
// Knowledge Base — Documents & Search
// ─────────────────────────────────────────────────────────────

export type KnowledgeDocumentType = "pdf" | "markdown" | "text" | "docx" | "url" | "git" | "json" | "csv" | "zip";
export type KnowledgeDocumentStatus = "pending" | "processing" | "indexed" | "failed";

export interface KnowledgeDocument {
  id: string;
  filename: string;
  document_type: KnowledgeDocumentType;
  version: string;
  author: string | null;
  tags: string[];
  status: KnowledgeDocumentStatus;
  error_message: string | null;
  file_size_bytes: number;
  page_count: number | null;
  chunk_count: number;
  uploaded_by_email: string | null;
  created_at: string;
}

export interface KnowledgeDocumentListResponse {
  total: number;
  documents: KnowledgeDocument[];
}

export interface KnowledgeSearchResult {
  document_id: string;
  filename: string;
  chunk_id: string;
  content: string;
  similarity_score: number;
  page_number: number | null;
  heading: string | null;
  section_path: string | null;
}

export interface KnowledgeSearchResponse {
  query: string;
  took_ms: number;
  results: KnowledgeSearchResult[];
}

// ─────────────────────────────────────────────────────────────
// Knowledge Ingestion Pipeline — Job Tracking
// ─────────────────────────────────────────────────────────────

export type KnowledgeJobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";
export type KnowledgeJobPriority = "low" | "normal" | "high" | "critical";

export type KnowledgePipelineStage =
  | "uploading"
  | "parsing"
  | "chunking"
  | "embedding"
  | "entity_extraction"
  | "graph_construction"
  | "vector_indexing"
  | "faq_detection"
  | "memory_sync"
  | "ready";

export interface KnowledgeJobResponse {
  job_id: string;
  document_id: string | null;
  document_name: string;
  connector_type: KnowledgeDocumentType;
  status: KnowledgeJobStatus;
  priority: KnowledgeJobPriority;
  stage: KnowledgePipelineStage | null;
  progress_percent: number;
  chunks_produced: number | null;
  entities_extracted: number | null;
  queued_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
}

export interface KnowledgeJobListResponse {
  total: number;
  jobs: KnowledgeJobResponse[];
}

// WebSocket progress events for knowledge ingestion pipeline
export interface KnowledgePipelineProgressEvent {
  type: "pipeline_progress";
  job_id: string;
  stage: KnowledgePipelineStage;
  progress_percent: number;
  message: string | null;
}

export interface KnowledgePipelineCompleteEvent {
  type: "pipeline_complete";
  job_id: string;
  chunks_produced: number;
  entities_extracted: number;
  duration_ms: number;
}

export interface KnowledgePipelineErrorEvent {
  type: "pipeline_error";
  job_id: string;
  error: string;
}

export interface WsPingEvent {
  type: "ping";
}

export type KnowledgeProgressEvent =
  | KnowledgePipelineProgressEvent
  | KnowledgePipelineCompleteEvent
  | KnowledgePipelineErrorEvent
  | WsPingEvent;

// ─────────────────────────────────────────────────────────────
// Assistant (Chat + RAG)
// ─────────────────────────────────────────────────────────────

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AssistantCitation {
  document_id: string;
  filename: string;
  page_number: number | null;
  section_path: string | null;
  heading: string | null;
  similarity_score: number;
  rerank_score: number;
  excerpt: string;
}

export interface AssistantRetrievalEvent {
  retrieved_count: number;
  confidence: number;
  citations: AssistantCitation[];
}

export interface AssistantInsufficientContextEvent {
  message: string;
  retrieved_count: number;
  confidence: number;
  latency_ms: number;
}

export interface AssistantDoneEvent {
  confidence: number;
  retrieved_count: number;
  latency_ms: number;
}

// ─────────────────────────────────────────────────────────────
// Graph Explorer
// ─────────────────────────────────────────────────────────────

export interface GraphNode {
  id: string;
  label: string;
  entity_type: string;
  document_id: string | null;
  chunk_count: number;
  confidence: number;
}

export interface GraphRelation {
  id: string;
  source_id: string;
  target_id: string;
  relation_type: string;
  weight: number;
}

export interface GraphSnapshot {
  nodes: GraphNode[];
  relations: GraphRelation[];
  total_nodes: number;
  total_relations: number;
  generated_at: string;
}

// ─────────────────────────────────────────────────────────────
// Memory Engine
// ─────────────────────────────────────────────────────────────

export interface MemoryEntry {
  id: string;
  session_id: string;
  memory_type: "conversation" | "long_term" | "task" | "organization";
  content_summary: string;
  embedding_count: number;
  created_at: string;
  last_accessed_at: string | null;
}

export interface MemoryState {
  total_entries: number;
  conversation_count: number;
  long_term_count: number;
  task_count: number;
  organization_count: number;
  total_embeddings: number;
  recent_entries: MemoryEntry[];
}

// ─────────────────────────────────────────────────────────────
// Knowledge Activity (My Activity + Team Activity)
// ─────────────────────────────────────────────────────────────

export interface RecentKnowledgeOperation {
  job_id: string;
  document_name: string;
  connector_type: KnowledgeDocumentType;
  status: KnowledgeJobStatus;
  chunks_produced: number | null;
  entities_extracted: number | null;
  finished_at: string | null;
}

export interface MyKnowledgeActivitySummary {
  total_operations: number;
  jobs_by_status: Record<string, number>;
  total_documents_processed: number;
  total_chunks_produced: number;
  total_entities_extracted: number;
  average_processing_time_seconds: number | null;
  average_confidence_score: number | null;
  recent_operations: RecentKnowledgeOperation[];
}

export interface TeamMemberActivity {
  user_id: string;
  email: string;
  full_name: string | null;
  total_operations: number;
  total_documents_processed: number;
  total_queries: number;
  average_confidence_score: number | null;
}

export interface TeamKnowledgeActivitySummary {
  total_operations: number;
  total_documents_processed: number;
  members: TeamMemberActivity[];
}

// ─────────────────────────────────────────────────────────────
// Executive Intelligence
// ─────────────────────────────────────────────────────────────

export interface KnowledgeSourceHealth {
  source_id: string;
  source_name: string;
  connector_type: KnowledgeDocumentType;
  chunk_count: number;
  entity_count: number;
  last_ingested_at: string | null;
  health_score: number;
}

export interface WeeklyKnowledgeTrendPoint {
  week_start: string;
  operations_count: number;
  documents_indexed: number;
  average_confidence: number | null;
  gap_clusters_identified: number;
}

export interface WeekOverWeekKnowledgeDelta {
  operations_this_week: number;
  operations_last_week: number;
  documents_this_week: number;
  documents_last_week: number;
  average_confidence_this_week: number | null;
  average_confidence_last_week: number | null;
}

export interface ExecutiveEvidenceSnapshot {
  generated_at: string;
  total_knowledge_sources: number;
  total_operations: number;
  total_documents_indexed: number;
  total_chunks: number;
  total_entities: number;
  portfolio_average_confidence: number | null;
  top_knowledge_sources: KnowledgeSourceHealth[];
  weekly_trend: WeeklyKnowledgeTrendPoint[];
  week_over_week: WeekOverWeekKnowledgeDelta | null;
}

export interface ExecutiveCitation {
  document_id: string;
  filename: string;
  page_number: number | null;
  section_path: string | null;
  heading: string | null;
  similarity_score: number;
  excerpt: string;
}

export interface ExecutiveEvidenceEvent {
  evidence: ExecutiveEvidenceSnapshot;
  citations: ExecutiveCitation[];
  kb_confidence: number;
  kb_retrieved_count: number;
}

export interface ExecutiveInsufficientEvent {
  message: string;
  latency_ms: number;
}

export interface ExecutiveDoneEvent {
  latency_ms: number;
}

// ─────────────────────────────────────────────────────────────
// Knowledge Evolution (Gap Analysis & FAQ Synthesis)
// ─────────────────────────────────────────────────────────────

export interface GapCluster {
  id: string;
  query_pattern: string;
  frequency: number;
  representative_queries: string[];
  suggested_faq: string | null;
  status: "pending" | "approved" | "promoted" | "dismissed";
  created_at: string;
}

export interface GapClusterListResponse {
  total: number;
  clusters: GapCluster[];
}

export interface FaqEntry {
  id: string;
  question: string;
  answer: string;
  confidence: number;
  source_document_ids: string[];
  created_at: string;
  promoted_from_gap_id: string | null;
}

export interface FaqListResponse {
  total: number;
  entries: FaqEntry[];
}

// ─────────────────────────────────────────────────────────────
// RAG Studio & Benchmarks
// ─────────────────────────────────────────────────────────────

export interface BenchmarkStage {
  stage: string;
  avg_duration_ms: number;
  detail: string | null;
}

export interface BenchmarkResult {
  ran_at: string;
  stages: BenchmarkStage[];
  total_duration_ms: number;
  documents_indexed: number;
  llm_configured: boolean;
}

export interface SearchAnalyticsRecentEntry {
  feature: string;
  query: string;
  result_count: number;
  top_score: number | null;
  latency_ms: number;
  created_at: string;
}

export interface SearchAnalyticsSummary {
  total_searches: number;
  average_latency_ms: number | null;
  average_result_count: number | null;
  zero_result_count: number;
  zero_result_rate: number | null;
  recent_searches: SearchAnalyticsRecentEntry[];
}

export interface FeedbackSummary {
  total_feedback: number;
  positive_count: number;
  negative_count: number;
  positive_rate: number | null;
}

// ─────────────────────────────────────────────────────────────
// Report Generation (NOVA Knowledge Reports)
// ─────────────────────────────────────────────────────────────

export type ReportType = "pdf" | "json" | "csv" | "knowledge_summary";

export interface ReportStatusDetail {
  report_type: ReportType;
  status: string;
  error_message?: string | null;
}

export interface ReportPathsResponse {
  operation_id: string;
  pdf_available: boolean;
  json_available: boolean;
  csv_available: boolean;
  reports: ReportStatusDetail[];
}

// ─────────────────────────────────────────────────────────────
// Confidence & Retrieval Tracing
// ─────────────────────────────────────────────────────────────

export interface ConfidenceVector {
  dense: number;
  sparse: number;
  graph: number;
  faq: number;
  exa_web: number;
  final: number;
}

export interface RetrievalTrace {
  session_id: string;
  query: string;
  pipeline_stages_used: string[];
  total_candidates: number;
  reranked_count: number;
  confidence: ConfidenceVector;
  latency_ms: number;
  citations: AssistantCitation[];
}
