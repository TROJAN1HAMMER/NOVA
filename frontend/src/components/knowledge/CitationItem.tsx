import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { Badge } from "../ui/Badge";
import { cn } from "../../lib/utils";

// Structural, not tied to one named type — AssistantCitation and
// FindingIntelligenceCitation (types/api.ts) both already have this exact
// shape, so either can be passed here without any type-level coupling.
export interface CitationLike {
  document_id: string;
  filename: string;
  page_number: number | null;
  section_path: string | null;
  heading: string | null;
  similarity_score: number;
  excerpt: string;
}

/** Collapsed by default: filename + match score. Expands to show the
 * section/page and the full matched excerpt — the "expandable citations"
 * both the AI Assistant (Milestone 2) and Finding Intelligence
 * (Milestone 3) panels need identically. */
export function CitationItem({ citation }: { citation: CitationLike }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="rounded-lg border border-border">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-xs"
      >
        <span className="min-w-0 flex-1 truncate font-medium text-foreground">
          {citation.filename}
          {citation.page_number != null && ` · p.${citation.page_number}`}
        </span>
        <span className="flex shrink-0 items-center gap-2 text-muted-foreground">
          <Badge tone="neutral">{Math.round(citation.similarity_score * 100)}% match</Badge>
          <ChevronDown className={cn("size-3.5 transition-transform duration-200", expanded && "rotate-180")} />
        </span>
      </button>
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <div className="border-t border-border px-3 py-2 text-xs text-muted-foreground">
              {citation.section_path && <p className="mb-1">{citation.section_path}</p>}
              <p className="whitespace-pre-wrap text-foreground">{citation.excerpt}</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function CitationList({ citations, title = "Sources" }: { citations: CitationLike[]; title?: string }) {
  if (citations.length === 0) return null;
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title} ({citations.length})
      </p>
      {citations.map((citation, index) => (
        <CitationItem key={`${citation.document_id}-${index}`} citation={citation} />
      ))}
    </div>
  );
}
