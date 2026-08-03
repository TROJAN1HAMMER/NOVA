import { useEffect, useRef, useState, type FormEvent } from "react";
import { Bot, Send, Sparkles, ThumbsDown, ThumbsUp, User as UserIcon, XCircle } from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, CardContent } from "../components/ui/Card";
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

function MessageBubble({ message }: { message: AssistantChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "flex size-8 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground",
        )}
      >
        {isUser ? <UserIcon className="size-4" /> : <Bot className="size-4" />}
      </div>
      <div className={cn("max-w-[75%] space-y-2", isUser && "flex flex-col items-end")}>
        <div
          className={cn(
            "rounded-xl px-4 py-2.5 text-sm",
            isUser ? "bg-primary text-primary-foreground" : "border border-border bg-card text-foreground",
            message.error && "border-danger/40 bg-danger/10 text-danger",
          )}
        >
          <p className="whitespace-pre-wrap">{message.error ? message.error : message.content}</p>
          {message.isStreaming && !message.content && (
            <span className="inline-flex gap-1 py-1">
              <span className="size-1.5 animate-pulse rounded-full bg-muted-foreground" />
              <span className="size-1.5 animate-pulse rounded-full bg-muted-foreground [animation-delay:0.15s]" />
              <span className="size-1.5 animate-pulse rounded-full bg-muted-foreground [animation-delay:0.3s]" />
            </span>
          )}
        </div>

        {!isUser && !message.isStreaming && !message.error && message.confidence != null && (
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <ConfidenceBadge confidence={message.confidence} />
            <span>{message.retrievedCount ?? 0} chunk(s) retrieved</span>
            {message.latencyMs != null && <span>{message.latencyMs}ms</span>}
            <FeedbackButtons messageId={message.id} />
          </div>
        )}

        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="w-full">
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
  const scrollAnchorRef = useRef<HTMLDivElement>(null);

  const loadSessions = async () => {
    try {
      const data = await fetchChatSessions();
      setSessions(data);
    } catch {
      // quiet fail on auth or network delay
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

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
      // quiet fail
    }
  };

  useEffect(() => {
    scrollAnchorRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!input.trim() || isSending) return;
    sendMessage(input, activeSessionId || undefined);
    setInput("");
    setTimeout(loadSessions, 2000);
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col">
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

      <div className="flex flex-1 overflow-hidden rounded-xl border border-border">
        <SessionSidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelectSession={handleSelectSession}
          onNewSession={handleNewSession}
          onDeleteSession={handleDeleteSession}
        />

        <Card className="flex flex-1 flex-col overflow-hidden border-0 rounded-none">
          <CardContent className="flex-1 space-y-4 overflow-y-auto p-4">
            {messages.length === 0 ? (
              <EmptyState
                icon={<Sparkles className="size-10" />}
                title="Ask the assistant anything"
                description='Try: "How often must passwords be rotated?" — answers are grounded in your uploaded documents.'
              />
            ) : (
              messages.map((message) => <MessageBubble key={message.id} message={message} />)
            )}
            <div ref={scrollAnchorRef} />
          </CardContent>

          <form onSubmit={handleSubmit} className="flex items-center gap-2 border-t border-border p-4">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question about your knowledge base…"
              className="flex-1 rounded-lg border border-border bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
              disabled={isSending}
            />
            {isSending ? (
              <Button type="button" variant="outline" onClick={stop}>
                <XCircle className="size-4" />
                Stop
              </Button>
            ) : (
              <Button type="submit" disabled={!input.trim()}>
                <Send className="size-4" />
                Send
              </Button>
            )}
          </form>
        </Card>
      </div>
    </div>
  );
}
