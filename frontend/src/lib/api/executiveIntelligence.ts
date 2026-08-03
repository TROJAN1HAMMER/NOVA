import { isAxiosError } from "axios";
import { apiClient } from "./client";
import { API_BASE_URL, tokenStorage } from "./client";
import type {
  ChatMessage,
  ExecutiveCitation,
  ExecutiveDoneEvent,
  ExecutiveEvidenceEvent,
  ExecutiveEvidenceSnapshot,
  ExecutiveInsufficientEvent,
} from "../../types/api";

// Same fetch+ReadableStream approach as lib/api/assistant.ts — POST body
// SSE isn't supported by the native EventSource API, so this bypasses
// apiClient (axios) for the streaming call only; the PDF export below is
// a plain POST and goes through apiClient as usual.
export interface ExecutiveIntelligenceStreamCallbacks {
  onEvidence: (event: ExecutiveEvidenceEvent) => void;
  onToken: (text: string) => void;
  onInsufficientContext: (event: ExecutiveInsufficientEvent) => void;
  onDone: (event: ExecutiveDoneEvent) => void;
  onError: (message: string) => void;
}

function dispatchEvent(rawEvent: string, callbacks: ExecutiveIntelligenceStreamCallbacks) {
  let eventType = "message";
  const dataLines: string[] = [];
  for (const line of rawEvent.split("\n")) {
    if (line.startsWith("event: ")) eventType = line.slice("event: ".length);
    else if (line.startsWith("data: ")) dataLines.push(line.slice("data: ".length));
  }
  const data = dataLines.join("\n");
  if (!data && eventType === "message") return;

  switch (eventType) {
    case "evidence":
      callbacks.onEvidence(JSON.parse(data));
      break;
    case "token":
      callbacks.onToken(data);
      break;
    case "insufficient_context":
      callbacks.onInsufficientContext(JSON.parse(data));
      break;
    case "done":
      callbacks.onDone(JSON.parse(data));
      break;
    case "error":
      callbacks.onError(data);
      break;
  }
}

export async function streamExecutiveIntelligence(
  payload: { question: string; history: ChatMessage[] },
  callbacks: ExecutiveIntelligenceStreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const token = tokenStorage.getAccessToken();
  const response = await fetch(`${API_BASE_URL}/executive-intelligence/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok || !response.body) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // response wasn't JSON — keep the generic status-based message
    }
    callbacks.onError(detail);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      dispatchEvent(buffer.slice(0, boundary), callbacks);
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");
    }
  }
}

async function extractErrorDetail(error: unknown): Promise<string> {
  if (!isAxiosError(error)) return "PDF export failed. Please try again.";
  const data = error.response?.data;
  if (data instanceof Blob) {
    try {
      const text = await data.text();
      const parsed = JSON.parse(text) as { detail?: string };
      if (typeof parsed.detail === "string") return parsed.detail;
    } catch {
      // not JSON — fall through
    }
  }
  if (!error.response) return "Could not reach the NOVA API. Check that it's running.";
  return `PDF export failed (HTTP ${error.response.status}).`;
}

export const executiveIntelligenceApi = {
  exportPdf: async (payload: {
    question: string;
    answer: string;
    evidence: ExecutiveEvidenceSnapshot;
    citations: ExecutiveCitation[];
    confidence: number | null;
  }): Promise<void> => {
    let response;
    try {
      response = await apiClient.post("/executive-intelligence/export-pdf", payload, { responseType: "blob" });
    } catch (error) {
      throw new Error(await extractErrorDetail(error), { cause: error });
    }
    const url = window.URL.createObjectURL(response.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = "NOVA-executive-intelligence.pdf";
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },
};
