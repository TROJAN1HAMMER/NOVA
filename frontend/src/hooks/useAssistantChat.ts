import { useCallback, useRef, useState } from "react";
import { streamAssistantChat } from "../lib/api/assistant";
import type { AssistantCitation, ChatMessage } from "../types/api";

export interface AssistantChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: AssistantCitation[];
  confidence?: number;
  retrievedCount?: number;
  latencyMs?: number;
  isInsufficientContext?: boolean;
  isStreaming?: boolean;
  error?: string;
}

export function useAssistantChat() {
  const [messages, setMessages] = useState<AssistantChatMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (text: string, sessionId?: string) => {
      const trimmed = text.trim();
      if (!trimmed || isSending) return;

      const history: ChatMessage[] = messages
        .filter((m) => !m.error && !m.isInsufficientContext)
        .map((m) => ({ role: m.role, content: m.content }));

      const assistantMessageId = crypto.randomUUID();
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "user", content: trimmed },
        { id: assistantMessageId, role: "assistant", content: "", isStreaming: true },
      ]);
      setIsSending(true);

      const controller = new AbortController();
      abortRef.current = controller;

      const patchAssistant = (patch: Partial<AssistantChatMessage>) => {
        setMessages((prev) => prev.map((m) => (m.id === assistantMessageId ? { ...m, ...patch } : m)));
      };

      try {
        await streamAssistantChat(
          { message: trimmed, history, session_id: sessionId },
          {
            onRetrieval: (event) =>
              patchAssistant({
                citations: event.citations,
                confidence: event.calibrated_trust_score ?? event.confidence,
                retrievedCount: event.retrieved_count,
              }),
            onToken: (text) =>
              setMessages((prev) =>
                prev.map((m) => (m.id === assistantMessageId ? { ...m, content: m.content + text } : m)),
              ),
            onInsufficientContext: (event) =>
              patchAssistant({
                content: event.message,
                isInsufficientContext: true,
                isStreaming: false,
                confidence: event.confidence,
                retrievedCount: event.retrieved_count,
                latencyMs: event.latency_ms,
              }),
            onDone: (event) =>
              patchAssistant({
                isStreaming: false,
                confidence: event.confidence,
                retrievedCount: event.retrieved_count,
                latencyMs: event.latency_ms,
              }),
            onError: (message) => patchAssistant({ isStreaming: false, error: message || "The assistant failed to respond." }),
          },
          controller.signal,
        );
      } catch (error) {
        if (!controller.signal.aborted) {
          patchAssistant({ isStreaming: false, error: error instanceof Error ? error.message : "Request failed." });
        }
      } finally {
        setIsSending(false);
        abortRef.current = null;
      }
    },
    [messages, isSending],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);
  const clear = useCallback(() => setMessages([]), []);

  return { messages, sendMessage, isSending, stop, clear, setMessages };
}
