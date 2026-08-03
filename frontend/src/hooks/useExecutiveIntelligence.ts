import { useCallback, useRef, useState } from "react";
import { streamExecutiveIntelligence } from "../lib/api/executiveIntelligence";
import type { ChatMessage, ExecutiveCitation, ExecutiveEvidenceSnapshot } from "../types/api";

export interface ExecutiveIntelligenceMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  evidence?: ExecutiveEvidenceSnapshot;
  citations?: ExecutiveCitation[];
  kbConfidence?: number;
  kbRetrievedCount?: number;
  latencyMs?: number;
  isInsufficientContext?: boolean;
  isStreaming?: boolean;
  error?: string;
}

/** Same client-side-only conversation-history model as useAssistantChat —
 * see backend/app/services/executive_intelligence/__init__.py. */
export function useExecutiveIntelligence() {
  const [messages, setMessages] = useState<ExecutiveIntelligenceMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (text: string) => {
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

      const patchAssistant = (patch: Partial<ExecutiveIntelligenceMessage>) => {
        setMessages((prev) => prev.map((m) => (m.id === assistantMessageId ? { ...m, ...patch } : m)));
      };

      try {
        await streamExecutiveIntelligence(
          { question: trimmed, history },
          {
            onEvidence: (event) =>
              patchAssistant({
                evidence: event.evidence,
                citations: event.citations,
                kbConfidence: event.kb_confidence,
                kbRetrievedCount: event.kb_retrieved_count,
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
                latencyMs: event.latency_ms,
              }),
            onDone: (event) => patchAssistant({ isStreaming: false, latencyMs: event.latency_ms }),
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

  return { messages, sendMessage, isSending, stop, clear };
}
