import { apiClient } from "./client";

export interface ScanJobStatusResponse {
  scan_job_id: string;
  repository_id: string;
  repository_name: string;
  status: string;
  priority: string;
  progress_percent: number;
  current_stage: string;
  retry_count: number;
  max_retries: number;
  timeout_seconds: number;
  queued_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  last_heartbeat_at: string | null;
  archived_at: string | null;
  error_message: string | null;
  total_findings: number | null;
  brs_score: number | null;
  brs_risk_level: string | null;
  attack_surface_exposure_score: number | null;
  attack_surface_exposure_level: string | null;
  summary: Record<string, any> | null;
  worker_status: Record<string, any>;
}

export interface ScanJobListResponse {
  total: number;
  scan_jobs: ScanJobStatusResponse[];
}

export interface ScanJobCreateResponse {
  scan_job_id: string;
  repository_id: string;
  status: string;
  priority: string;
  message: string;
}

export interface FindingResponse {
  id: string;
  scan_job_id: string;
  title: string;
  severity: string;
  category: string;
  source: string;
  sources: string[];
  occurrence_count: number;
  cvss: number;
  brs: number;
  brs_risk_level: string;
  file_path: string;
  line_number: number;
  description: string;
  package?: string;
  package_version?: string;
  cve?: string;
  cwe_id?: string;
  cwe_name?: string;
  owasp_category?: string;
  owasp_name?: string;
  mitre_technique_ids: string[];
  ai_explanation?: string;
  ai_business_impact?: string;
  ai_remediation?: string;
  compliance?: {
    rbi_clause?: string;
    pci_clause?: string;
    swift_clause?: string;
  };
}

export interface FindingsListResponse {
  scan_job_id: string;
  total: number;
  findings: FindingResponse[];
}

export interface ComplianceEngineResultSchema {
  scan_job_id: string;
  frameworks: Array<{
    framework_name: string;
    short_code: string;
    version: string;
    total_controls: number;
    passed_controls: number;
    failed_controls: number;
    compliance_percentage: number;
    controls: Array<{
      requirement_id: string;
      title: string;
      description: string;
      status: string;
      recommendation?: string;
      evidence: Array<{
        finding_title: string;
        severity: string;
        file_path: string;
        line_number: number;
        source: string;
      }>;
    }>;
  }>;
  overall_compliance_percentage: number;
}

export const scanApi = {
  listScans: async (params?: { status?: string; limit?: number; offset?: number }): Promise<ScanJobListResponse> => {
    const response = await apiClient.get<ScanJobListResponse>("/scan", { params });
    return response.data;
  },

  getScanStatus: async (scanJobId: string): Promise<ScanJobStatusResponse> => {
    const response = await apiClient.get<ScanJobStatusResponse>(`/scan/${scanJobId}`);
    return response.data;
  },

  submitRepository: async (payload: { repo_url: string; ref?: string; priority?: string; max_retries?: number; timeout_seconds?: number }): Promise<ScanJobCreateResponse> => {
    const response = await apiClient.post<ScanJobCreateResponse>("/scan/repository", payload);
    return response.data;
  },

  triggerPremadeScan: async (riskLevel: string): Promise<ScanJobCreateResponse> => {
    const response = await apiClient.post<ScanJobCreateResponse>(`/scan/premade/${riskLevel}`);
    return response.data;
  },

  cancelScanJob: async (scanJobId: string): Promise<ScanJobStatusResponse> => {
    const response = await apiClient.post<ScanJobStatusResponse>(`/scan/${scanJobId}/cancel`);
    return response.data;
  },

  getScanFindings: async (scanJobId: string): Promise<FindingsListResponse> => {
    const response = await apiClient.get<FindingsListResponse>(`/scan/${scanJobId}/findings`);
    return response.data;
  },

  getScanCompliance: async (scanJobId: string): Promise<ComplianceEngineResultSchema> => {
    const response = await apiClient.get<ComplianceEngineResultSchema>(`/scan/${scanJobId}/compliance`);
    return response.data;
  }
};
