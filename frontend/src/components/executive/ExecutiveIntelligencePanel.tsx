import { useEffect, useRef, useState, type FormEvent } from "react";
import { motion } from "framer-motion";
import { Bot, Download, Info, Send, Sparkles, User as UserIcon, XCircle } from "lucide-react";
import { Card, CardContent, CardHeader } from "../ui/Card";
import { Button } from "../ui/Button";
import { EmptyState } from "../ui/EmptyState";
import { CitationList } from "../knowledge/CitationItem";
import { ExecutiveMarkdown } from "./ExecutiveMarkdown";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { EvidenceHighlights } from "./EvidenceHighlights";
import { useExecutiveIntelligence, type ExecutiveIntelligenceMessage } from "../../hooks/useExecutiveIntelligence";
import { executiveIntelligenceApi } from "../../lib/api/executiveIntelligence";
import { useToast } from "../../hooks/useToast";
import { splitStreamedSections } from "../../lib/markdownSections";
import { cn } from "../../lib/utils";

const SUGGESTED_QUESTIONS = [
  "What are our biggest risks?",
  "What changed this week?",
  "What compliance gaps remain?",
  "What should leadership prioritize?",
];

function MessageBubble({
  message,
  question,
  onSuggested,
}: {
  message: ExecutiveIntelligenceMessage;
  question: string | undefined;
  onSuggested: (question: string) => void;
}) {
  const isUser = message.role === "user";
  const toast = useToast();
  const [isExporting, setIsExporting] = useState(false);

  const canExport =
    !isUser && !message.isStreaming && !message.error && !message.isInsufficientContext && message.evidence;
  const showEvidence = !isUser && !message.isInsufficientContext && !message.error;

  const handleExport = async () => {
    if (!message.evidence || !question) return;
    setIsExporting(true);
    try {
      await executiveIntelligenceApi.exportPdf({
        question,
        answer: message.content,
        evidence: message.evidence,
        citations: message.citations ?? [],
        confidence: message.kbConfidence ?? null,
      });
      toast.success("PDF exported", "Your executive intelligence report has been downloaded.");
    } catch (error) {
      toast.error("Export failed", error instanceof Error ? error.message : "Please try again.");
    } finally {
      setIsExporting(false);
    }
  };

  const streamedSections = !isUser && message.isStreaming ? splitStreamedSections(message.content) : null;
  const relatedQuestions = SUGGESTED_QUESTIONS.filter((suggestion) => suggestion !== question);

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

      <div className={cn("w-full min-w-0 space-y-2 sm:max-w-[85%] lg:max-w-3xl", isUser && "flex flex-col items-end")}>
        {isUser ? (
          <div className="rounded-xl bg-primary px-4 py-2.5 text-sm text-primary-foreground">
            <p className="whitespace-pre-wrap">{message.content}</p>
          </div>
        ) : message.error ? (
          <div className="rounded-xl border border-danger/40 bg-danger/10 px-4 py-2.5 text-sm text-danger">
            <p className="whitespace-pre-wrap">{message.error}</p>
          </div>
        ) : message.isInsufficientContext ? (
          <div className="w-full rounded-xl border border-dashed border-border bg-muted/40 px-4 py-3">
            <div className="flex items-start gap-2 text-sm text-muted-foreground">
              <Info className="mt-0.5 size-4 shrink-0" />
              <p>{message.content}</p>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {relatedQuestions.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => onSuggested(suggestion)}
                  className="rounded-full border border-border px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-muted"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="w-full min-w-0 rounded-xl border border-border bg-card px-4 py-3">
            {message.isStreaming && !message.content ? (
              <span className="inline-flex gap-1 py-1">
                <span className="size-1.5 animate-pulse rounded-full bg-muted-foreground" />
                <span className="size-1.5 animate-pulse rounded-full bg-muted-foreground [animation-delay:0.15s]" />
                <span className="size-1.5 animate-pulse rounded-full bg-muted-foreground [animation-delay:0.3s]" />
              </span>
            ) : streamedSections ? (
              <>
                {streamedSections.complete.map((section, index) => (
                  <motion.div
                    key={index}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.25, ease: "easeOut" }}
                  >
                    <ExecutiveMarkdown>{section}</ExecutiveMarkdown>
                  </motion.div>
                ))}
                {streamedSections.trailing && (
                  <p className="whitespace-pre-wrap text-sm text-foreground">
                    {streamedSections.trailing}
                    <span className="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse-slow bg-muted-foreground align-middle" />
                  </p>
                )}
              </>
            ) : (
              <ExecutiveMarkdown>{message.content}</ExecutiveMarkdown>
            )}
          </div>
        )}

        {showEvidence && message.evidence && (
          <div className="w-full space-y-2">
            <EvidenceHighlights evidence={message.evidence} />
            {!message.isStreaming && <ConfidenceBadge confidence={message.kbConfidence ?? null} />}
          </div>
        )}

        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="w-full">
            <CitationList citations={message.citations} title="Supporting Evidence" />
          </div>
        )}

        {canExport && (
          <Button variant="outline" size="sm" onClick={handleExport} isLoading={isExporting}>
            <Download className="size-3.5" />
            Export to PDF
          </Button>
        )}
      </div>
    </div>
  );
}

export function ExecutiveIntelligencePanel() {
  const { messages, sendMessage, isSending, stop, clear } = useExecutiveIntelligence();
  const [input, setInput] = useState("");
  const scrollAnchorRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollAnchorRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!input.trim() || isSending) return;
    sendMessage(input);
    setInput("");
  };

  const handleSuggested = (question: string) => {
    if (isSending) return;
    sendMessage(question);
  };

  return (
    <Card className="flex h-[42rem] flex-col overflow-hidden">
      <CardHeader
        title="Executive Intelligence"
        description="Ask a question — answers are grounded in your scan history first, knowledge base second."
        action={
          messages.length > 0 ? (
            <Button variant="outline" size="sm" onClick={clear} disabled={isSending}>
              Clear conversation
            </Button>
          ) : undefined
        }
      />

      <CardContent className="flex-1 space-y-4 overflow-y-auto">
        {messages.length === 0 ? (
          <div className="space-y-4">
            <EmptyState
              icon={<Sparkles className="size-10" />}
              title="Ask leadership's questions directly"
              description="Every answer is grounded in real scan history and cites its evidence — nothing is invented."
            />
            <div className="flex flex-wrap justify-center gap-2">
              {SUGGESTED_QUESTIONS.map((question) => (
                <button
                  key={question}
                  type="button"
                  onClick={() => handleSuggested(question)}
                  className="rounded-full border border-border px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-muted"
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((message, index) => {
            const precedingUserMessage = message.role === "assistant" ? messages[index - 1] : undefined;
            return (
              <MessageBubble
                key={message.id}
                message={message}
                question={precedingUserMessage?.content}
                onSuggested={handleSuggested}
              />
            );
          })
        )}
        <div ref={scrollAnchorRef} />
      </CardContent>

      <form onSubmit={handleSubmit} className="flex items-center gap-2 border-t border-border p-4">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. What should leadership prioritize?"
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
            Ask
          </Button>
        )}
      </form>
    </Card>
  );
}
