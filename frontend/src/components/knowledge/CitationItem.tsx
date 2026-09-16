import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, FileText, ExternalLink, Globe, ShieldAlert, Cpu } from "lucide-react";
import { cn } from "../../lib/utils";

export interface CitationLike {
  document_id: string;
  filename: string;
  page_number: number | null;
  section_path: string | null;
  heading: string | null;
  similarity_score: number;
  excerpt: string;
  source_type?: string;
  url?: string | null;
  domain?: string | null;
  published_at?: string | null;
  file_path?: string | null;
  line_number?: number | null;
  severity?: string | null;
  cwe_id?: string | null;
  cve?: string | null;
}

export function CitationItem({ citation }: { citation: CitationLike }) {
  const [expanded, setExpanded] = useState(false);
  const hasValidScore = typeof citation.similarity_score === "number" && !isNaN(citation.similarity_score) && citation.similarity_score > 0;
  const matchPct = hasValidScore ? Math.round(citation.similarity_score * 100) : null;
  const isExternal = citation.source_type?.toLowerCase() === "external_web";
  const isSecurity = citation.source_type?.toLowerCase() === "security_finding";
  const isArchitecture = citation.source_type?.toLowerCase()?.startsWith("architecture");

  return (
    <div
      className={cn(
        "rounded-xl border border-border/80 bg-card/50 backdrop-blur-sm shadow-xs transition-all hover:bg-card/75 overflow-hidden",
        isExternal ? "hover:border-sky-500/40" : isSecurity ? "hover:border-amber-500/40" : "hover:border-primary/30"
      )}
    >
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center justify-between gap-3 px-3.5 py-2.5 text-left text-xs transition-colors hover:bg-muted/40"
      >
        <span className="min-w-0 flex-1 truncate font-medium text-foreground flex items-center gap-2">
          {isExternal ? (
            <Globe className="size-3.5 text-sky-400 shrink-0" />
          ) : isSecurity ? (
            <ShieldAlert className="size-3.5 text-amber-400 shrink-0" />
          ) : isArchitecture ? (
            <Cpu className="size-3.5 text-emerald-400 shrink-0" />
          ) : (
            <FileText className="size-3.5 text-primary shrink-0" />
          )}

          <span className="truncate">{citation.filename || (isExternal ? "External Web Resource" : "Knowledge Document")}</span>

          {citation.domain && (
            <span className="text-[10px] rounded-md bg-sky-500/10 px-1.5 py-0.5 border border-sky-500/20 text-sky-400 shrink-0 font-mono">
              {citation.domain}
            </span>
          )}

          {citation.page_number != null && (
            <span className="text-[10px] rounded-md bg-muted/80 px-1.5 py-0.5 border border-border text-muted-foreground shrink-0 font-mono">
              p.{citation.page_number}
            </span>
          )}
        </span>

        <span className="flex shrink-0 items-center gap-2">
          <span
            className={cn(
              "rounded-full px-2.5 py-0.5 text-[10px] font-semibold font-mono border",
              isExternal
                ? "bg-sky-500/10 text-sky-400 border-sky-500/25"
                : isSecurity
                ? "bg-amber-500/10 text-amber-400 border-amber-500/25"
                : "bg-primary/10 text-primary border-primary/25"
            )}
          >
            {matchPct != null ? `${matchPct}% match` : isExternal ? "Web Verified" : "Vector Grounded"}
          </span>
          <ChevronDown
            className={cn(
              "size-3.5 text-muted-foreground transition-transform duration-200",
              expanded && "rotate-180 text-primary"
            )}
          />
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
            <div className="border-t border-border/70 bg-card/40 px-3.5 py-3 text-xs text-foreground space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono text-muted-foreground">
                {citation.section_path && (
                  <div className="flex items-center gap-1.5 text-primary">
                    <ExternalLink className="size-3 shrink-0" />
                    <span>{citation.section_path}</span>
                  </div>
                )}
                {citation.url && (
                  <a
                    href={citation.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-sky-400 hover:text-sky-300 hover:underline"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Globe className="size-3 shrink-0" />
                    <span className="truncate max-w-xs">{citation.url}</span>
                    <ExternalLink className="size-2.5 shrink-0 opacity-70" />
                  </a>
                )}
                {citation.published_at && (
                  <span className="text-[10px] text-muted-foreground/80">
                    Published: {new Date(citation.published_at).toLocaleDateString()}
                  </span>
                )}
              </div>

              <p className="whitespace-pre-wrap font-mono text-[11px] text-muted-foreground leading-relaxed bg-background/80 p-3 rounded-lg border border-border/70">
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

  const externalCount = citations.filter((c) => c.source_type?.toLowerCase() === "external_web").length;
  const internalCount = citations.length - externalCount;

  return (
    <div className="space-y-2 pt-1">
      <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-muted-foreground px-1">
        <span>{title} ({citations.length})</span>
        <span className="text-[10px] font-mono text-muted-foreground/80 flex items-center gap-1.5">
          {externalCount > 0 ? (
            <>
              {internalCount > 0 && <span>Internal ({internalCount})</span>}
              {internalCount > 0 && <span>•</span>}
              <span className="text-sky-400">External Web ({externalCount})</span>
            </>
          ) : (
            "Vector Grounded"
          )}
        </span>
      </div>
      <div className="space-y-2">
        {citations.map((citation, index) => (
          <CitationItem key={`${citation.document_id}-${index}`} citation={citation} />
        ))}
      </div>
    </div>
  );
}
