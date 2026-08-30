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
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10px] font-bold font-mono border shadow-sm",
        isHigh
          ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300 shadow-emerald-950/20"
          : isMid
          ? "border-amber-500/40 bg-amber-500/10 text-amber-300 shadow-amber-950/20"
          : "border-cyan-500/40 bg-cyan-500/10 text-cyan-300 shadow-cyan-950/20"
      )}
    >
      <Zap className="size-3 text-cyan-400 animate-pulse" />
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
          "rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-800 hover:text-emerald-400 disabled:pointer-events-none",
          submitted === 1 && "text-emerald-400 bg-emerald-950/50 border border-emerald-500/30"
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
          "rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-800 hover:text-rose-400 disabled:pointer-events-none",
          submitted === -1 && "text-rose-400 bg-rose-950/50 border border-rose-500/30"
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
    bannerStyle = "border-amber-500/40 bg-gradient-to-r from-amber-950/40 via-slate-900/90 to-slate-900 text-amber-200 shadow-amber-950/20";
    icon = <ShieldAlert className="size-4 text-amber-400 shrink-0" />;
    title = <span className="text-amber-300">Answer withheld — Conflicting evidence detected</span>;
  } else if (isWarning) {
    bannerStyle = "border-amber-500/40 bg-gradient-to-r from-amber-950/40 via-slate-900/90 to-slate-900 text-amber-200 shadow-amber-950/20";
    icon = <ShieldAlert className="size-4 text-amber-400 shrink-0" />;
    title = <span className="text-amber-300">Warning — Low evidence confidence</span>;
  } else {
    bannerStyle = "border-emerald-500/40 bg-gradient-to-r from-emerald-950/40 via-slate-900/90 to-slate-900 text-emerald-200 shadow-emerald-950/20";
    icon = <CheckCircle2 className="size-4 text-emerald-400 shrink-0" />;
    title = <span className="text-emerald-300">Answer grounded in verified documents</span>;
  }

  return (
    <div
      className={cn(
        "w-full rounded-2xl border p-3.5 text-xs space-y-2.5 backdrop-blur-md transition-all shadow-md",
        bannerStyle
      )}
    >
      <div className="flex items-center justify-between font-semibold">
        <span className="flex items-center gap-2 text-xs font-bold tracking-wide">
          {icon}
          {title}
        </span>
        <Badge tone={isBlock || isWarning ? "warning" : "success"}>{explanation.policy_trigger}</Badge>
      </div>

      <p className="text-slate-300 leading-relaxed text-xs font-sans">{explanation.explanation}</p>

      {explanation.contradicting_evidence && explanation.contradicting_evidence.length > 0 && (
        <details className="mt-2 text-xs border-t border-slate-800/80 pt-2 cursor-pointer group">
          <summary className="font-semibold text-amber-300 hover:underline flex items-center gap-1.5">
            <span>Inspect NLI Evidence Reasoning & Contradictions</span>
            <ChevronDown className="size-3 transition-transform group-open:rotate-180 text-amber-400" />
          </summary>
          <div className="mt-2.5 space-y-2 font-mono text-[11px]">
            {explanation.contradicting_evidence.map((ev, idx) => (
              <div key={idx} className="rounded-xl border border-slate-800 bg-slate-950/80 p-3 space-y-1">
                <div className="flex items-center justify-between text-slate-200 font-medium">
                  <span className="text-amber-400 font-bold">
                    Evidence {idx === 0 ? "A" : "B"}: {ev.file_path ? `${ev.file_path}:${ev.line_number || 1}` : ev.filename}
                  </span>
                  {ev.severity && <Badge tone={ev.severity === "CRITICAL" || ev.severity === "HIGH" ? "danger" : "warning"}>{ev.severity}</Badge>}
                </div>
                {ev.security_property && <div className="text-slate-400 text-[10px]">Property: {ev.security_property}</div>}
                {ev.cwe_id && <div className="text-slate-400 text-[10px]">CWE: {ev.cwe_id} {ev.cve ? `| CVE: ${ev.cve}` : ""}</div>}
                <p className="mt-1 text-slate-300 text-[11px] whitespace-pre-wrap leading-relaxed">{ev.excerpt}</p>
              </div>
            ))}
            <div className="flex flex-wrap gap-4 text-[10px] text-slate-400 pt-1.5 border-t border-slate-800/60">
              <span>Relationship: <strong className="text-slate-200">{explanation.evidence_relationship}</strong></span>
              <span>NLI Confidence: <strong className="text-slate-200">{Math.round(explanation.nli_confidence * 100)}%</strong></span>
              <span>Agreement Score: <strong className="text-slate-200">{explanation.agreement_score}</strong></span>
              <span>Trust Score: <strong className="text-slate-200">{explanation.trust_score}</strong></span>
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
      initial={{ opacity: 0, y: 12, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.22, ease: "easeOut" }}
      className={cn("flex gap-3.5 w-full", isUser && "flex-row-reverse")}
    >
      {/* Avatar */}
      <div
        className={cn(
          "flex size-9 shrink-0 items-center justify-center rounded-2xl mt-0.5 shadow-lg transition-transform hover:scale-105",
          isUser
            ? "bg-gradient-to-br from-cyan-500 via-teal-500 to-blue-600 text-slate-950 shadow-cyan-500/20"
            : "bg-slate-900 border border-cyan-500/30 text-cyan-300 shadow-cyan-950/40 relative"
        )}
      >
        {isUser ? (
          <UserIcon className="size-4 font-bold" />
        ) : (
          <>
            <Bot className="size-4 text-cyan-400" />
            <span className="absolute -top-1 -right-1 size-2 rounded-full bg-cyan-400 animate-ping" />
          </>
        )}
      </div>

      {/* Content Container */}
      <div className={cn("flex flex-col gap-2 min-w-0", isUser ? "items-end max-w-[75%]" : "items-start w-full max-w-[88%]")}>
        {/* Safety Gate Banner */}
        {!isUser && !message.isStreaming && message.safetyExplanation && (
          <SafetyGateBanner explanation={message.safetyExplanation} />
        )}

        <div
          className={cn(
            "rounded-2xl px-5 py-3.5 text-sm leading-relaxed break-words w-full shadow-lg transition-all",
            isUser
              ? "bg-gradient-to-r from-cyan-600 via-teal-600 to-blue-600 text-white font-medium shadow-cyan-900/30 rounded-tr-sm"
              : "bg-slate-900/80 backdrop-blur-xl border border-slate-800 text-slate-200 shadow-slate-950/40 rounded-tl-sm hover:border-cyan-500/30",
            message.error && "border-rose-500/40 bg-rose-950/20 text-rose-300 shadow-rose-950/30"
          )}
        >
          {message.isStreaming && !message.content ? (
            <div className="flex items-center gap-2 py-1 text-xs text-cyan-400 font-mono">
              <Sparkles className="size-4 animate-spin text-cyan-400" />
              <span>Ollama LLM generating token stream…</span>
            </div>
          ) : (
            <p className="whitespace-pre-wrap leading-relaxed font-sans">{message.error ?? message.content}</p>
          )}
        </div>

        {/* Metadata Footer */}
        {!isUser && !message.isStreaming && !message.error && message.confidence != null && (
          <div className="flex flex-wrap items-center gap-2.5 text-xs text-slate-400 px-1 py-0.5 font-mono text-[11px]">
            <ConfidenceBadge confidence={message.confidence} />
            <span className="rounded-md bg-slate-900 px-2 py-0.5 border border-slate-800 text-slate-400">
              {message.retrievedCount || message.citations?.length || 0} chunk(s) retrieved
            </span>
            {message.latencyMs != null && (
              <span className="rounded-md bg-slate-900 px-2 py-0.5 border border-slate-800 text-slate-400">
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
      color: "from-cyan-500/20 to-teal-500/20 text-cyan-400 border-cyan-500/30",
    },
    {
      icon: Calendar,
      label: "Academic Holidays",
      prompt: "What holidays are provided in the Fall Semester 2026-27 Academic Calendar?",
      color: "from-purple-500/20 to-indigo-500/20 text-purple-400 border-purple-500/30",
    },
    {
      icon: Lock,
      label: "PCI-DSS Banking Security",
      prompt: "What does PCI-DSS Requirement 7.1 enforce for administrative APIs?",
      color: "from-emerald-500/20 to-teal-500/20 text-emerald-400 border-emerald-500/30",
    },
    {
      icon: ShieldCheck,
      label: "OWASP FAPI Controls",
      prompt: "What security controls mitigate FAPI-01 Broken Object Level Authorization?",
      color: "from-amber-500/20 to-orange-500/20 text-amber-400 border-amber-500/30",
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
              className="border-slate-800 bg-slate-900 text-slate-300 hover:border-cyan-500/40 hover:text-cyan-300"
            >
              Clear View
            </Button>
          ) : undefined
        }
      />

      {/* Main Glassmorphic Workspace */}
      <div className="flex flex-1 overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/80 backdrop-blur-2xl shadow-2xl min-h-0 relative">
        {/* Background Grid Particle Glow */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-cyan-900/10 via-slate-950 to-slate-950 pointer-events-none" />

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
            className="flex-1 overflow-y-auto overflow-x-hidden px-5 py-5 space-y-6 scroll-smooth"
            style={{ scrollbarWidth: "thin" }}
          >
            {messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center p-6 text-center">
                <motion.div
                  initial={{ scale: 0.9, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ duration: 0.4 }}
                  className="max-w-xl space-y-6"
                >
                  <div className="relative mx-auto flex size-20 items-center justify-center rounded-3xl bg-gradient-to-br from-cyan-500/20 via-teal-500/10 to-indigo-500/20 border border-cyan-500/30 shadow-2xl shadow-cyan-500/10">
                    <Sparkles className="size-10 text-cyan-400 animate-pulse" />
                    <span className="absolute -top-1 -right-1 size-3.5 rounded-full bg-cyan-400 animate-ping" />
                  </div>

                  <div className="space-y-2">
                    <h3 className="text-xl font-bold tracking-tight text-slate-100">
                      NOVA RAG Intelligence Assistant
                    </h3>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Ask questions about your uploaded documents, security standards, and institutional policies.
                      Answers are grounded using vector search with local <code className="text-cyan-400 font-mono">Ollama (llama3.2:3b)</code>.
                    </p>
                  </div>

                  {/* Sample Interactive Chips */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 text-left">
                    {samplePrompts.map((item, idx) => {
                      const IconComp = item.icon;
                      return (
                        <motion.button
                          key={idx}
                          whileHover={{ scale: 1.02, translateY: -2 }}
                          whileTap={{ scale: 0.98 }}
                          onClick={() => handleSendPrompt(item.prompt)}
                          className={cn(
                            "flex items-start gap-3 rounded-2xl border p-3.5 transition-all shadow-md bg-slate-900/60 backdrop-blur-md cursor-pointer group hover:shadow-cyan-950/40",
                            item.color
                          )}
                        >
                          <div className="rounded-xl p-2 bg-slate-950/80 border border-slate-800 shrink-0 group-hover:border-cyan-500/40">
                            <IconComp className="size-4" />
                          </div>
                          <div className="space-y-1 min-w-0">
                            <div className="text-xs font-bold text-slate-200 group-hover:text-cyan-300 transition-colors flex items-center justify-between">
                              <span>{item.label}</span>
                              <Zap className="size-3 text-cyan-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                            </div>
                            <p className="text-[11px] text-slate-400 truncate">{item.prompt}</p>
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
                onClick={scrollToBottom}
                className="absolute bottom-3 right-6 flex items-center gap-1.5 rounded-full border border-cyan-500/30 bg-slate-900/90 px-3.5 py-1.5 text-xs text-cyan-300 shadow-xl backdrop-blur-md transition hover:bg-cyan-950 hover:border-cyan-400"
              >
                <ChevronDown className="size-3.5" />
                <span>Scroll to latest</span>
              </button>
            </div>
          )}

          {/* Input Dock Bar */}
          <div className="border-t border-slate-800/80 bg-slate-950/90 backdrop-blur-xl px-5 py-3.5">
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
                  className="w-full rounded-2xl border border-slate-800 bg-slate-900/90 px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-cyan-500/60 focus:ring-2 focus:ring-cyan-500/20 shadow-inner disabled:opacity-50"
                  disabled={isSending}
                />
                <div className="absolute right-3 top-2.5 flex items-center gap-1.5 pointer-events-none">
                  <span className="flex items-center gap-1 rounded-full bg-cyan-950/80 border border-cyan-500/30 px-2 py-0.5 text-[10px] font-mono text-cyan-300">
                    <Cpu className="size-3 text-cyan-400 animate-pulse" />
                    <span>ollama:llama3.2:3b</span>
                  </span>
                </div>
              </div>

              {isSending ? (
                <Button
                  type="button"
                  variant="outline"
                  onClick={stop}
                  className="shrink-0 border-rose-500/40 bg-rose-950/30 text-rose-300 hover:bg-rose-900/50 rounded-xl"
                >
                  <XCircle className="size-4" />
                  Stop
                </Button>
              ) : (
                <Button
                  type="submit"
                  disabled={!input.trim()}
                  className="shrink-0 rounded-xl bg-gradient-to-r from-cyan-500 via-teal-500 to-blue-600 font-bold text-slate-950 shadow-lg shadow-cyan-500/20 hover:scale-105 hover:shadow-cyan-500/40 active:scale-95 disabled:opacity-40 disabled:hover:scale-100"
                >
                  <Send className="size-4" />
                  <span>Send</span>
                </Button>
              )}
            </form>
            <div className="mt-2 flex items-center justify-between text-[11px] text-slate-500 px-1 font-mono">
              <span>Press <kbd className="rounded border border-slate-800 bg-slate-900 px-1 py-0.5 text-[10px] text-slate-400">Enter</kbd> to query</span>
              <span className="text-cyan-400/80">Local Vector RAG Engine Active</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
