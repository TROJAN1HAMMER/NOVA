import { API_BASE_URL, apiClient, tokenStorage } from "./client";
import type {
  AssistantDoneEvent,
  AssistantInsufficientContextEvent,
  AssistantRetrievalEvent,
  ChatMessage,
} from "../../types/api";

export interface ChatSessionItem {
  id: string;
  title: string;
  context_summary?: string;
  created_at: string;
}

export interface SavedChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  citations: any[];
  confidence_vector: Record<string, number>;
  calibrated_trust_score?: number;
  reasoning_trace: Record<string, any>;
  created_at: string;
}

export interface AssistantStreamCallbacks {
  onRetrieval: (event: AssistantRetrievalEvent & { session_id?: string; confidence_vector?: any; calibrated_trust_score?: number; reasoning_trace?: any }) => void;
  onToken: (text: string) => void;
  onInsufficientContext: (event: AssistantInsufficientContextEvent) => void;
  onDone: (event: AssistantDoneEvent) => void;
  onError: (message: string) => void;
}

export async function fetchChatSessions(): Promise<ChatSessionItem[]> {
  const { data } = await apiClient.get<ChatSessionItem[]>("/assistant/sessions");
  return data;
}

export async function createChatSession(title?: string): Promise<ChatSessionItem> {
  const { data } = await apiClient.post<ChatSessionItem>("/assistant/sessions", { title });
  return data;
}

export async function fetchSessionMessages(sessionId: string): Promise<SavedChatMessage[]> {
  const { data } = await apiClient.get<SavedChatMessage[]>(`/assistant/sessions/${sessionId}/messages`);
  return data;
}

export async function deleteChatSession(sessionId: string): Promise<void> {
  await apiClient.delete(`/assistant/sessions/${sessionId}`);
}

function dispatchEvent(rawEvent: string, callbacks: AssistantStreamCallbacks) {
  let eventType = "message";
  const dataLines: string[] = [];
  for (const line of rawEvent.split("\n")) {
    if (line.startsWith("event: ")) eventType = line.slice("event: ".length);
    else if (line.startsWith("data: ")) dataLines.push(line.slice("data: ".length));
  }
  const data = dataLines.join("\n");
  if (!data && eventType === "message") return;

  switch (eventType) {
    case "retrieval":
      callbacks.onRetrieval(JSON.parse(data));
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

export async function streamAssistantChat(
  payload: { message: string; history: ChatMessage[]; session_id?: string },
  callbacks: AssistantStreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const token = tokenStorage.getAccessToken();
  const response = await fetch(`${API_BASE_URL}/assistant/chat`, {
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
      // response wasn't JSON
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
