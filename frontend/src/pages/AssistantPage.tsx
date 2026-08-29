import { useEffect, useRef, useState, useCallback, type FormEvent } from "react";
import { Bot, Send, Sparkles, ThumbsDown, ThumbsUp, User as UserIcon, XCircle, ChevronDown, ShieldAlert, CheckCircle2 } from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { CitationList } from "../components/knowledge/CitationItem";
import { SessionSidebar } from "../components/assistant/SessionSidebar";
import { useAssistantChat, type AssistantChatMessage } from "../hooks/useAssistantChat";
import { useSubmitFeedback } from "../hooks/useRagOperations";
import {
  fetchChatSessions,
  createChatSession,
  deleteChatSession,
  fetchSessionMessages,
  type ChatSessionItem,
} from "../lib/api/assistant";
import { cn } from "../lib/utils";

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  const tone = confidence >= 0.75 ? "success" : confidence >= 0.5 ? "warning" : "danger";
  return <Badge tone={tone}>{pct}% calibrated trust</Badge>;
}

function FeedbackButtons({ messageId }: { messageId: string }) {
  const submitFeedback = useSubmitFeedback();
  const [submitted, setSubmitted] = useState<1 | -1 | null>(null);

  const handleClick = (rating: 1 | -1) => {
    if (submitted) return;
    setSubmitted(rating);
    submitFeedback.mutate({ feature: "assistant_chat", reference_id: messageId, rating });
  };

  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        onClick={() => handleClick(1)}
        disabled={Boolean(submitted)}
        aria-label="Helpful"
        className={cn(
          "rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-success disabled:pointer-events-none",
          submitted === 1 && "text-success",
        )}
      >
        <ThumbsUp className="size-3.5" />
      </button>
      <button
        type="button"
        onClick={() => handleClick(-1)}
        disabled={Boolean(submitted)}
        aria-label="Not helpful"
        className={cn(
          "rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-danger disabled:pointer-events-none",
          submitted === -1 && "text-danger",
        )}
      >
        <ThumbsDown className="size-3.5" />
      </button>
    </div>
  );
}

function SafetyGateBanner({ explanation }: { explanation: NonNullable<AssistantChatMessage["safetyExplanation"]> }) {
  const isBlock = explanation.policy_trigger === "CRITICAL_CONTRADICTION" || explanation.decision === "FALLBACK_WEB" || explanation.decision === "ABSTAIN";

  return (
    <div className={cn(
      "w-full rounded-xl border p-3.5 text-xs space-y-2.5 transition-all",
      isBlock ? "border-amber-500/40 bg-amber-500/10 text-amber-200" : "border-emerald-500/30 bg-emerald-500/10 text-emerald-200"
    )}>
      <div className="flex items-center justify-between font-semibold">
        <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
          {isBlock ? (
            <>
              <ShieldAlert className="size-4 text-amber-400 shrink-0" />
              <span className="text-amber-400">Answer withheld because conflicting evidence was detected</span>
            </>
          ) : (
            <>
              <CheckCircle2 className="size-4 text-emerald-400 shrink-0" />
              <span className="text-emerald-400">Answer generated from trusted evidence</span>
            </>
          )}
        </span>
        <Badge tone={isBlock ? "warning" : "success"}>{explanation.policy_trigger}</Badge>
      </div>

      <p className="text-muted-foreground leading-relaxed text-xs">{explanation.explanation}</p>

      {/* Contradiction Evidence Inspection Component */}
      {explanation.contradicting_evidence && explanation.contradicting_evidence.length > 0 && (
        <details className="mt-2 text-xs border-t border-border/40 pt-2 cursor-pointer group">
          <summary className="font-semibold text-amber-300 hover:underline flex items-center gap-1">
            <span>Inspect Contradictory Evidence Details & NLI Reasoning</span>
            <ChevronDown className="size-3 transition-transform group-open:rotate-180" />
          </summary>
          <div className="mt-2.5 space-y-2 font-mono text-[11px]">
            {explanation.contradicting_evidence.map((ev, idx) => (
              <div key={idx} className="rounded-lg border border-border/60 bg-card p-2.5 space-y-1">
                <div className="flex items-center justify-between text-foreground font-medium">
                  <span className="text-amber-400 font-bold">
                    Evidence {idx === 0 ? "A" : "B"}: {ev.file_path ? `${ev.file_path}:${ev.line_number || 1}` : ev.filename}
                  </span>
                  {ev.severity && <Badge tone={ev.severity === "CRITICAL" || ev.severity === "HIGH" ? "danger" : "warning"}>{ev.severity}</Badge>}
                </div>
                {ev.security_property && <div className="text-muted-foreground text-[10px]">Property: {ev.security_property}</div>}
                {ev.cwe_id && <div className="text-muted-foreground text-[10px]">CWE: {ev.cwe_id} {ev.cve ? `| CVE: ${ev.cve}` : ""}</div>}
                <p className="mt-1 text-muted-foreground text-[11px] whitespace-pre-wrap leading-relaxed">{ev.excerpt}</p>
              </div>
            ))}
            <div className="flex flex-wrap gap-4 text-[10px] text-muted-foreground pt-1 border-t border-border/30">
              <span>Relationship: <strong className="text-foreground">{explanation.evidence_relationship}</strong></span>
              <span>NLI Confidence: <strong className="text-foreground">{Math.round(explanation.nli_confidence * 100)}%</strong></span>
              <span>Agreement Score: <strong className="text-foreground">{explanation.agreement_score}</strong></span>
              <span>Trust Score: <strong className="text-foreground">{explanation.trust_score}</strong></span>
            </div>
          </div>
        </details>
      )}
    </div>
  );
}

function MessageBubble({ message }: { message: AssistantChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex gap-3 w-full", isUser && "flex-row-reverse")}>
      {/* Avatar */}
      <div
        className={cn(
          "flex size-8 shrink-0 items-center justify-center rounded-full mt-1",
          isUser ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground",
        )}
      >
        {isUser ? <UserIcon className="size-4" /> : <Bot className="size-4" />}
      </div>

      {/* Bubble */}
      <div className={cn("flex flex-col gap-2 min-w-0", isUser ? "items-end max-w-[70%]" : "items-start w-full max-w-[85%]")}>
        {/* Safety Gate Banner */}
        {!isUser && !message.isStreaming && message.safetyExplanation && (
          <SafetyGateBanner explanation={message.safetyExplanation} />
        )}

        <div
          className={cn(
            "rounded-2xl px-4 py-3 text-sm leading-relaxed break-words w-full",
            isUser
              ? "bg-primary text-primary-foreground"
              : "border border-border bg-card text-foreground",
            message.error && "border-danger/40 bg-danger/10 text-danger",
          )}
        >
          {message.isStreaming && !message.content ? (
            <span className="inline-flex gap-1 py-1">
              <span className="size-2 animate-bounce rounded-full bg-muted-foreground" />
              <span className="size-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:0.15s]" />
              <span className="size-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:0.3s]" />
            </span>
          ) : (
            <p className="whitespace-pre-wrap">{message.error ?? message.content}</p>
          )}
        </div>

        {/* Metadata */}
        {!isUser && !message.isStreaming && !message.error && message.confidence != null && (
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground px-1">
            <ConfidenceBadge confidence={message.confidence} />
            <span>{message.retrievedCount ?? 0} chunk(s) retrieved</span>
            {message.latencyMs != null && <span>{message.latencyMs}ms</span>}
            <FeedbackButtons messageId={message.id} />
          </div>
        )}

        {/* Citations */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="w-full px-1">
            <CitationList citations={message.citations} />
          </div>
        )}
      </div>
    </div>
  );
}

export default function AssistantPage() {
  const { messages, sendMessage, isSending, stop, clear, setMessages } = useAssistantChat();
  const [input, setInput] = useState("");
  const [sessions, setSessions] = useState<ChatSessionItem[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [showScrollBtn, setShowScrollBtn] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);

  const loadSessions = async () => {
    try {
      const data = await fetchChatSessions();
      setSessions(data);
    } catch {
      // quiet fail
    }
  };

  useEffect(() => { loadSessions(); }, []);

  // Track if user is near bottom
  const handleScroll = useCallback(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    isNearBottomRef.current = distFromBottom < 80;
    setShowScrollBtn(distFromBottom > 200);
  }, []);

  // Auto-scroll only when user is already near bottom
  useEffect(() => {
    if (isNearBottomRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    setShowScrollBtn(false);
  };

  const handleSelectSession = async (id: string) => {
    setActiveSessionId(id);
    try {
      const msgs = await fetchSessionMessages(id);
      setMessages(
        msgs.map((m) => ({
          id: m.id,
          role: m.role as "user" | "assistant",
          content: m.content,
          citations: m.citations,
          confidence: m.calibrated_trust_score ?? undefined,
        }))
      );
    } catch {
      clear();
    }
  };

  const handleNewSession = async () => {
    try {
      const newSess = await createChatSession();
      setActiveSessionId(newSess.id);
      clear();
      await loadSessions();
    } catch {
      clear();
      setActiveSessionId(null);
    }
  };

  const handleDeleteSession = async (id: string) => {
    try {
      await deleteChatSession(id);
      if (activeSessionId === id) { setActiveSessionId(null); clear(); }
      await loadSessions();
    } catch { /* quiet fail */ }
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!input.trim() || isSending) return;
    // Force scroll to bottom on new message send
    isNearBottomRef.current = true;
    sendMessage(input, activeSessionId || undefined);
    setInput("");
    setTimeout(loadSessions, 2000);
  };

  return (
    <div className="flex h-[calc(100vh-6rem)] flex-col gap-3">
      <PageHeader
        title="AI Assistant"
        description="Ask questions in plain language — answers are grounded in your indexed knowledge base documents."
        action={
          messages.length > 0 ? (
            <Button variant="outline" size="sm" onClick={clear} disabled={isSending}>
              Clear View
            </Button>
          ) : undefined
        }
      />

      {/* Main chat area */}
      <div className="flex flex-1 overflow-hidden rounded-xl border border-border min-h-0">
        {/* Session Sidebar */}
        <SessionSidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelectSession={handleSelectSession}
          onNewSession={handleNewSession}
          onDeleteSession={handleDeleteSession}
        />

        {/* Chat Panel */}
        <div className="flex flex-1 flex-col min-h-0 overflow-hidden bg-card">
          {/* ── Scrollable messages area ── */}
          <div
            ref={scrollContainerRef}
            onScroll={handleScroll}
            className="flex-1 overflow-y-auto overflow-x-hidden px-4 py-4 space-y-5 scroll-smooth"
            style={{ scrollbarWidth: "thin" }}
          >
            {messages.length === 0 ? (
              <div className="flex h-full items-center justify-center">
                <EmptyState
                  icon={<Sparkles className="size-10" />}
                  title="Ask the assistant anything"
                  description='Try: "How often must passwords be rotated?" — answers are grounded in your uploaded documents.'
                />
              </div>
            ) : (
              messages.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))
            )}
            {/* Scroll anchor */}
            <div ref={messagesEndRef} className="h-1" />
          </div>

          {/* Scroll-to-bottom FAB */}
          {showScrollBtn && (
            <div className="relative">
              <button
                onClick={scrollToBottom}
                className="absolute bottom-2 right-4 z-10 flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground shadow-md transition hover:bg-muted"
              >
                <ChevronDown className="size-3.5" />
                Scroll to latest
              </button>
            </div>
          )}

          {/* ── Input bar ── */}
          <div className="border-t border-border bg-card/80 backdrop-blur-sm px-4 py-3">
            <form onSubmit={handleSubmit} className="flex items-center gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit(e as unknown as FormEvent);
                  }
                }}
                placeholder="Ask a question about your knowledge base…"
                className="flex-1 rounded-xl border border-border bg-background px-4 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 disabled:opacity-50"
                disabled={isSending}
              />
              {isSending ? (
                <Button type="button" variant="outline" onClick={stop} className="shrink-0">
                  <XCircle className="size-4" />
                  Stop
                </Button>
              ) : (
                <Button type="submit" disabled={!input.trim()} className="shrink-0">
                  <Send className="size-4" />
                  Send
                </Button>
              )}
            </form>
            <p className="mt-1.5 text-center text-xs text-muted-foreground">
              Press <kbd className="rounded border border-border px-1 py-0.5 font-mono text-[10px]">Enter</kbd> to send · answers grounded in your documents
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
