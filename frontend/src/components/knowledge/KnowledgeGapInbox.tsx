import { CheckCircle2, Sparkles } from "lucide-react";
import type { FAQRuleItem } from "../../lib/api/faq";

interface KnowledgeGapInboxProps {
  draftRules: FAQRuleItem[];
  onPromoteRule: (id: string) => Promise<void>;
}

export function KnowledgeGapInbox({ draftRules, onPromoteRule }: KnowledgeGapInboxProps) {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-border bg-accent/40 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <Sparkles className="size-4 text-amber-500" />
          Outer-Loop Self-Healing Knowledge Gap Inbox
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          The outer-loop self-healing worker clusters recurring retrieval failures from search telemetry to auto-synthesize draft candidate axioms.
          Candidates remain unverified until reviewed and promoted by an administrator.
        </p>
      </div>

      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="px-4 py-3 border-b border-border font-semibold text-sm flex items-center justify-between">
          <span>Pending Knowledge Gap Candidates ({draftRules.length})</span>
          <span className="text-xs text-muted-foreground font-normal">Awaiting Human-in-the-Loop Promotion</span>
        </div>
        <table className="w-full text-left text-sm">
          <thead className="bg-muted/50 text-xs font-medium text-muted-foreground uppercase">
            <tr>
              <th className="px-4 py-2">Synthesized Cluster Pattern</th>
              <th className="px-4 py-2">Proposed Answer (Candidate Draft)</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {draftRules.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-xs text-muted-foreground">
                  No knowledge gap candidates pending. The self-healing loop has resolved all failure clusters!
                </td>
              </tr>
            ) : (
              draftRules.map((rule) => (
                <tr key={rule.id} className="hover:bg-muted/30">
                  <td className="px-4 py-3 font-medium text-foreground">
                    <span className="font-mono text-xs text-amber-400 bg-amber-950/40 px-2 py-0.5 rounded border border-amber-500/20">
                      {rule.keyword}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground text-xs leading-relaxed max-w-md">
                    {rule.response}
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-300 border border-amber-500/30">
                      Draft Candidate
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => onPromoteRule(rule.id)}
                      className="inline-flex items-center gap-1.5 rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 transition-colors shadow-sm"
                    >
                      <CheckCircle2 className="size-3.5" />
                      Promote to Active FAQ
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
