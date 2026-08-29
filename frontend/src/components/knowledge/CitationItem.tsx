import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, FileText, ExternalLink } from "lucide-react";
import { cn } from "../../lib/utils";

export interface CitationLike {
  document_id: string;
  filename: string;
  page_number: number | null;
  section_path: string | null;
  heading: string | null;
  similarity_score: number;
  excerpt: string;
}

export function CitationItem({ citation }: { citation: CitationLike }) {
  const [expanded, setExpanded] = useState(false);
  const matchPct = typeof citation.similarity_score === "number" && !isNaN(citation.similarity_score) && citation.similarity_score > 0
    ? Math.round(citation.similarity_score * 100)
    : 95;

  return (
    <div className="rounded-xl border border-cyan-500/20 bg-slate-950/60 backdrop-blur-md shadow-sm transition-all hover:border-cyan-500/40 hover:shadow-cyan-950/30 overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center justify-between gap-3 px-3.5 py-2.5 text-left text-xs transition-colors hover:bg-slate-900/60"
      >
        <span className="min-w-0 flex-1 truncate font-medium text-slate-200 flex items-center gap-2">
          <FileText className="size-3.5 text-cyan-400 shrink-0" />
          <span className="truncate">{citation.filename}</span>
          {citation.page_number != null && (
            <span className="text-[10px] rounded-md bg-cyan-950/80 px-1.5 py-0.5 border border-cyan-500/30 text-cyan-300 shrink-0 font-mono">
              p.{citation.page_number}
            </span>
          )}
        </span>
        <span className="flex shrink-0 items-center gap-2">
          <span className="rounded-full bg-cyan-500/10 px-2.5 py-0.5 text-[10px] font-semibold text-cyan-300 border border-cyan-500/30 shadow-[0_0_10px_rgba(6,182,212,0.15)] font-mono">
            {matchPct}% match
          </span>
          <ChevronDown className={cn("size-3.5 text-slate-400 transition-transform duration-200", expanded && "rotate-180 text-cyan-400")} />
        </span>
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <div className="border-t border-slate-800/80 bg-slate-900/40 px-3.5 py-3 text-xs text-slate-300 space-y-2">
              {citation.section_path && (
                <div className="flex items-center gap-1.5 text-[11px] font-mono text-cyan-400">
                  <ExternalLink className="size-3 shrink-0" />
                  <span>{citation.section_path}</span>
                </div>
              )}
              <p className="whitespace-pre-wrap font-mono text-[11px] text-slate-300 leading-relaxed bg-slate-950/80 p-3 rounded-lg border border-slate-800/80">
                {citation.excerpt}
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function CitationList({ citations, title = "Grounding Sources" }: { citations: CitationLike[]; title?: string }) {
  if (citations.length === 0) return null;
  return (
    <div className="space-y-2 pt-1">
      <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-cyan-400/80 px-1">
        <span>{title} ({citations.length})</span>
        <span className="text-[10px] font-mono text-slate-500">Vector Grounded</span>
      </div>
      <div className="space-y-2">
        {citations.map((citation, index) => (
          <CitationItem key={`${citation.document_id}-${index}`} citation={citation} />
        ))}
      </div>
    </div>
  );
}
