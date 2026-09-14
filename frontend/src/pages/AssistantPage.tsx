import { useEffect, useRef, useState, useCallback, type FormEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Bot,
  Send,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  User as UserIcon,
  XCircle,
  ChevronDown,
  ShieldAlert,
  CheckCircle2,
  Cpu,
  GraduationCap,
  Calendar,
  Lock,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
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
  const isHigh = confidence >= 0.75;
  const isMid = confidence >= 0.5;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10px] font-bold font-mono border shadow-2xs",
        isHigh
          ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
          : isMid
          ? "border-amber-500/30 bg-amber-500/10 text-amber-400"
          : "border-rose-500/30 bg-rose-500/10 text-rose-400"
      )}
    >
      <Zap className={cn("size-3", isHigh ? "text-emerald-400" : isMid ? "text-amber-400" : "text-rose-400")} />
      <span>{pct}% calibrated trust</span>
    </span>
  );
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
          "rounded-lg p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-emerald-400 disabled:pointer-events-none",
          submitted === 1 && "text-emerald-400 bg-emerald-500/10 border border-emerald-500/30"
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
          "rounded-lg p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-rose-400 disabled:pointer-events-none",
          submitted === -1 && "text-rose-400 bg-rose-500/10 border border-rose-500/30"
        )}
      >
        <ThumbsDown className="size-3.5" />
      </button>
    </div>
  );
}

function SafetyGateBanner({ explanation }: { explanation: NonNullable<AssistantChatMessage["safetyExplanation"]> }) {
  const isBlock = explanation.decision === "FALLBACK_WEB" || explanation.decision === "ABSTAIN";
  const isWarning = explanation.decision === "GENERATE_WITH_WARNING" || explanation.policy_trigger === "LOW_RETRIEVAL_SIMILARITY" || explanation.policy_trigger === "SECURITY_QUERY_LOW_CONFIDENCE";

  let bannerStyle = "";
  let icon = null;
  let title = null;

  if (isBlock) {
    bannerStyle = "border-danger/40 bg-danger/10 text-danger shadow-xs";
    icon = <ShieldAlert className="size-4 text-danger shrink-0" />;
    title = <span className="text-danger font-semibold">Answer withheld — Conflicting evidence detected</span>;
  } else if (isWarning) {
    bannerStyle = "border-warning/40 bg-warning/10 text-warning shadow-xs";
    icon = <ShieldAlert className="size-4 text-warning shrink-0" />;
    title = <span className="text-warning font-semibold">Warning — Low evidence confidence</span>;
  } else {
    bannerStyle = "border-emerald-500/30 bg-emerald-500/10 text-emerald-300 shadow-xs";
    icon = <CheckCircle2 className="size-4 text-emerald-400 shrink-0" />;
    title = <span className="text-emerald-300 font-semibold">Answer grounded in verified documents</span>;
  }

  return (
    <div
      className={cn(
        "w-full rounded-xl border p-3.5 text-xs space-y-2.5 backdrop-blur-md transition-all shadow-xs",
        bannerStyle
      )}
    >
      <div className="flex items-center justify-between font-semibold">
        <span className="flex items-center gap-2 text-xs font-semibold tracking-wide">
          {icon}
          {title}
        </span>
        <Badge tone={isBlock ? "danger" : isWarning ? "warning" : "success"}>{explanation.policy_trigger}</Badge>
      </div>

      <p className="text-muted-foreground leading-relaxed text-xs font-sans">{explanation.explanation}</p>

      {explanation.contradicting_evidence && explanation.contradicting_evidence.length > 0 && (
        <details className="mt-2 text-xs border-t border-border/70 pt-2 cursor-pointer group">
          <summary className="font-semibold text-warning hover:underline flex items-center gap-1.5">
            <span>Inspect NLI Evidence Reasoning & Contradictions</span>
            <ChevronDown className="size-3 transition-transform group-open:rotate-180 text-warning" />
          </summary>
          <div className="mt-2.5 space-y-2 font-mono text-[11px]">
            {explanation.contradicting_evidence.map((ev, idx) => (
              <div key={idx} className="rounded-lg border border-border bg-card/80 p-3 space-y-1">
                <div className="flex items-center justify-between text-foreground font-medium">
                  <span className="text-warning font-semibold">
                    Evidence {idx === 0 ? "A" : "B"}: {ev.file_path ? `${ev.file_path}:${ev.line_number || 1}` : ev.filename}
                  </span>
                  {ev.severity && <Badge tone={ev.severity === "CRITICAL" || ev.severity === "HIGH" ? "danger" : "warning"}>{ev.severity}</Badge>}
                </div>
                {ev.security_property && <div className="text-muted-foreground text-[10px]">Property: {ev.security_property}</div>}
                {ev.cwe_id && <div className="text-muted-foreground text-[10px]">CWE: {ev.cwe_id} {ev.cve ? `| CVE: ${ev.cve}` : ""}</div>}
                <p className="mt-1 text-muted-foreground text-[11px] whitespace-pre-wrap leading-relaxed">{ev.excerpt}</p>
              </div>
            ))}
            <div className="flex flex-wrap gap-4 text-[10px] text-muted-foreground pt-1.5 border-t border-border/60">
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
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className={cn("flex gap-3 w-full", isUser && "flex-row-reverse")}
    >
      {/* Avatar */}
      <div
        className={cn(
          "flex size-8 shrink-0 items-center justify-center rounded-xl mt-0.5 shadow-2xs transition-transform",
          isUser
            ? "bg-secondary text-secondary-foreground border border-border/80"
            : "bg-primary/10 text-primary border border-primary/25 relative"
        )}
      >
        {isUser ? (
          <UserIcon className="size-4 font-semibold" />
        ) : (
          <Bot className="size-4 text-primary" />
        )}
      </div>

      {/* Content Container */}
      <div className={cn("flex flex-col gap-1.5 min-w-0", isUser ? "items-end max-w-[75%]" : "items-start w-full max-w-[88%]")}>
        {/* Safety Gate Banner */}
        {!isUser && !message.isStreaming && message.safetyExplanation && (
          <SafetyGateBanner explanation={message.safetyExplanation} />
        )}

        <div
          className={cn(
            "rounded-xl px-4.5 py-3 text-sm leading-relaxed break-words w-full shadow-xs transition-colors",
            isUser
              ? "bg-secondary/90 border border-border/80 text-foreground font-medium rounded-tr-xs"
              : "bg-card/65 backdrop-blur-md border border-border/80 text-foreground rounded-tl-xs hover:border-border",
            message.error && "border-danger/40 bg-danger/10 text-danger shadow-xs"
          )}
        >
          {message.isStreaming && !message.content ? (
            <div className="flex items-center gap-2 py-1 text-xs text-primary font-mono">
              <Sparkles className="size-4 animate-spin text-primary" />
              <span>Ollama LLM generating token stream…</span>
            </div>
          ) : (
            <p className="whitespace-pre-wrap leading-relaxed font-sans">{message.error ?? message.content}</p>
          )}
        </div>

        {/* Metadata Footer */}
        {!isUser && !message.isStreaming && !message.error && message.confidence != null && (
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground px-1 py-0.5 font-mono text-[11px]">
            <ConfidenceBadge confidence={message.confidence} />
            <span className="rounded-md bg-muted/60 px-2 py-0.5 border border-border/60 text-muted-foreground">
              {message.retrievedCount || message.citations?.length || 0} chunk(s) retrieved
            </span>
            {message.latencyMs != null && (
              <span className="rounded-md bg-muted/60 px-2 py-0.5 border border-border/60 text-muted-foreground">
                {message.latencyMs}ms
              </span>
            )}
            <FeedbackButtons messageId={message.id} />
          </div>
        )}

        {/* Citations */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="w-full px-0.5">
            <CitationList citations={message.citations} />
          </div>
        )}
      </div>
    </motion.div>
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

  useEffect(() => {
    loadSessions();
  }, []);

  const handleScroll = useCallback(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    isNearBottomRef.current = distFromBottom < 80;
    setShowScrollBtn(distFromBottom > 200);
  }, []);

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
      if (activeSessionId === id) {
        setActiveSessionId(null);
        clear();
      }
      await loadSessions();
    } catch {
      /* quiet fail */
    }
  };

  const handleSendPrompt = (promptText: string) => {
    if (isSending) return;
    isNearBottomRef.current = true;
    sendMessage(promptText, activeSessionId || undefined);
    setTimeout(loadSessions, 2000);
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!input.trim() || isSending) return;
    handleSendPrompt(input.trim());
    setInput("");
  };

  const samplePrompts = [
    {
      icon: GraduationCap,
      label: "College Identification",
      prompt: "What college is the document based of?",
    },
    {
      icon: Calendar,
      label: "Academic Holidays",
      prompt: "What holidays are provided in the Fall Semester 2026-27 Academic Calendar?",
    },
    {
      icon: Lock,
      label: "PCI-DSS Banking Security",
      prompt: "What does PCI-DSS Requirement 7.1 enforce for administrative APIs?",
    },
    {
      icon: ShieldCheck,
      label: "OWASP FAPI Controls",
      prompt: "What security controls mitigate FAPI-01 Broken Object Level Authorization?",
    },
  ];

  return (
    <div className="flex h-[calc(100vh-6rem)] flex-col gap-3 relative">
      <PageHeader
        title="AI Assistant"
        description="Ask questions in plain language — answers are grounded in your indexed knowledge base documents."
        action={
          messages.length > 0 ? (
            <Button
              variant="outline"
              size="sm"
              onClick={clear}
              disabled={isSending}
            >
              Clear View
            </Button>
          ) : undefined
        }
      />

      {/* Main Workspace */}
      <div className="flex flex-1 overflow-hidden rounded-xl border border-border/80 bg-card/45 backdrop-blur-xl shadow-lg min-h-0 relative">
        {/* Session Sidebar */}
        <SessionSidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelectSession={handleSelectSession}
          onNewSession={handleNewSession}
          onDeleteSession={handleDeleteSession}
        />

        {/* Chat Canvas Area */}
        <div className="flex flex-1 flex-col min-h-0 overflow-hidden relative z-10">
          {/* Scrollable messages area */}
          <div
            ref={scrollContainerRef}
            onScroll={handleScroll}
            className="flex-1 overflow-y-auto overflow-x-hidden px-6 py-6 space-y-6 scroll-smooth"
            style={{ scrollbarWidth: "thin" }}
          >
            {messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center p-6 text-center">
                <motion.div
                  initial={{ scale: 0.95, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ duration: 0.3 }}
                  className="max-w-xl space-y-6"
                >
                  <div className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-primary/10 border border-primary/25 text-primary shadow-xs">
                    <Sparkles className="size-7 text-primary" />
                  </div>

                  <div className="space-y-1.5">
                    <h3 className="text-lg font-semibold tracking-tight text-foreground">
                      NOVA RAG Intelligence Assistant
                    </h3>
                    <p className="text-xs text-muted-foreground leading-relaxed max-w-md mx-auto">
                      Ask questions about your uploaded documents, security standards, and institutional policies.
                      Answers are grounded using vector search with local <code className="text-primary font-mono font-medium">Ollama (llama3.2:3b)</code>.
                    </p>
                  </div>

                  {/* Sample Interactive Chips */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 text-left">
                    {samplePrompts.map((item, idx) => {
                      const IconComp = item.icon;
                      return (
                        <motion.button
                          key={idx}
                          whileHover={{ scale: 1.01, translateY: -2 }}
                          whileTap={{ scale: 0.99 }}
                          onClick={() => handleSendPrompt(item.prompt)}
                          className="flex items-start gap-3 rounded-xl border border-border/80 bg-card/60 hover:bg-card/90 hover:border-primary/40 p-3.5 transition-all text-left group cursor-pointer shadow-xs hover:shadow-md"
                        >
                          <div className="rounded-lg p-2 bg-muted/70 border border-border/70 group-hover:border-primary/30 text-primary shrink-0 transition-colors">
                            <IconComp className="size-4 text-primary" />
                          </div>
                          <div className="space-y-1 min-w-0 flex-1">
                            <div className="text-xs font-semibold text-foreground group-hover:text-primary transition-colors flex items-center justify-between">
                              <span>{item.label}</span>
                              <Zap className="size-3 text-primary opacity-0 group-hover:opacity-100 transition-opacity" />
                            </div>
                            <p className="text-[11px] text-muted-foreground truncate">{item.prompt}</p>
                          </div>
                        </motion.button>
                      );
                    })}
                  </div>
                </motion.div>
              </div>
            ) : (
              <AnimatePresence initial={false}>
                {messages.map((message) => (
                  <MessageBubble key={message.id} message={message} />
                ))}
              </AnimatePresence>
            )}
            {/* Scroll anchor */}
            <div ref={messagesEndRef} className="h-2" />
          </div>

          {/* Scroll to bottom FAB */}
          {showScrollBtn && (
            <div className="relative z-20">
              <button
                type="button"
                onClick={scrollToBottom}
                className="absolute bottom-3 right-6 flex items-center gap-1.5 rounded-full border border-border bg-card/90 px-3.5 py-1.5 text-xs text-foreground shadow-lg backdrop-blur-md transition hover:bg-muted hover:border-primary/40"
              >
                <ChevronDown className="size-3.5 text-primary" />
                <span>Scroll to latest</span>
              </button>
            </div>
          )}

          {/* Input Dock Bar */}
          <div className="border-t border-border/80 bg-card/60 backdrop-blur-md px-5 py-3.5">
            <form onSubmit={handleSubmit} className="flex items-center gap-3">
              <div className="relative flex-1">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSubmit(e as unknown as FormEvent);
                    }
                  }}
                  placeholder="Ask a question about your documents…"
                  className="w-full rounded-xl border border-border bg-background/90 px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 shadow-inner transition-colors disabled:opacity-50"
                  disabled={isSending}
                />
                <div className="absolute right-3 top-2 flex items-center gap-1.5 pointer-events-none">
                  <span className="flex items-center gap-1 rounded-md bg-muted/80 border border-border px-2 py-0.5 text-[10px] font-mono text-muted-foreground">
                    <Cpu className="size-3 text-muted-foreground" />
                    <span>ollama:llama3.2:3b</span>
                  </span>
                </div>
              </div>

              {isSending ? (
                <Button
                  type="button"
                  variant="danger"
                  onClick={stop}
                  className="shrink-0 gap-1.5 rounded-lg px-3.5 py-2 text-xs font-semibold"
                >
                  <XCircle className="size-4" />
                  <span>Stop</span>
                </Button>
              ) : (
                <Button
                  type="submit"
                  variant="primary"
                  disabled={!input.trim()}
                  className="shrink-0 gap-1.5 rounded-lg px-4 py-2 font-semibold shadow-xs"
                >
                  <Send className="size-4" />
                  <span>Send</span>
                </Button>
              )}
            </form>
            <div className="mt-2 flex items-center justify-between text-[11px] text-muted-foreground px-1 font-mono">
              <span>Press <kbd className="rounded border border-border bg-muted/70 px-1 py-0.5 text-[10px] text-muted-foreground font-mono">Enter</kbd> to query</span>
              <span className="flex items-center gap-1.5 text-muted-foreground">
                <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
                <span>Local Vector RAG Engine Active</span>
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
