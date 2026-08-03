import { isAxiosError } from "axios";
import { apiClient } from "./client";
import type { ReportPathsResponse, ReportType } from "../../types/api";

/**
 * With `responseType: "blob"`, axios hands back a Blob for error responses
 * too (it never gets to parse the body as JSON) — so a 409 "still
 * generating" or 404 from the backend would otherwise surface as an opaque
 * blob with no readable message. Re-read it as text/JSON so callers get the
 * backend's actual `detail` string instead of silently failing.
 */
async function extractErrorDetail(error: unknown): Promise<string> {
  if (!isAxiosError(error)) return "Download failed. Please try again.";
  const data = error.response?.data;
  if (data instanceof Blob) {
    try {
      const text = await data.text();
      const parsed = JSON.parse(text) as { detail?: string };
      if (typeof parsed.detail === "string") return parsed.detail;
    } catch {
      // Not JSON (or empty) — fall through to a generic message below.
    }
  }
  if (!error.response) return "Could not reach the NOVA API. Check that it's running.";
  return `Download failed (HTTP ${error.response.status}).`;
}

export const reportsApi = {
  getStatus: async (scanJobId: string): Promise<ReportPathsResponse> => {
    const response = await apiClient.get<ReportPathsResponse>(`/reports/${scanJobId}`);
    return response.data;
  },

  // Report downloads stream a file (or 307-redirect to a presigned S3 URL),
  // so this can't go through a plain <a href> — the bearer token has to
  // ride an Authorization header, not a query param, to reach the file.
  download: async (scanJobId: string, reportType: ReportType, fileName: string): Promise<void> => {
    console.info("[reports] download requested", { scanJobId, reportType });
    console.info("[reports] download started", { scanJobId, reportType });
    let response;
    try {
      response = await apiClient.get(`/reports/${scanJobId}/download/${reportType}`, {
        responseType: "blob",
      });
    } catch (error) {
      const detail = await extractErrorDetail(error);
      console.error("[reports] download failed", { scanJobId, reportType, detail });
      throw new Error(detail, { cause: error });
    }
    const url = window.URL.createObjectURL(response.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
    console.info("[reports] download completed", { scanJobId, reportType });
  },
};
