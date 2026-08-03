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
          The background AI clusterer automatically synthesizes draft FAQ candidates from accumulated retrieval failures. Click <strong>Promote</strong> to convert a gap into an instant 0ms FAQ rule.
        </p>
      </div>

      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="px-4 py-3 border-b border-border font-semibold text-sm">
          Pending Knowledge Gap Candidates ({draftRules.length})
        </div>
        <table className="w-full text-left text-sm">
          <thead className="bg-muted/50 text-xs font-medium text-muted-foreground uppercase">
            <tr>
              <th className="px-4 py-2">Synthesized Keyword Cluster</th>
              <th className="px-4 py-2">Proposed Answer Response</th>
              <th className="px-4 py-2 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {draftRules.length === 0 ? (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center text-xs text-muted-foreground">
                  No knowledge gap candidates pending. The self-healing loop has resolved all failure clusters!
                </td>
              </tr>
            ) : (
              draftRules.map((rule) => (
                <tr key={rule.id} className="hover:bg-muted/30">
                  <td className="px-4 py-3 font-medium text-foreground">{rule.keyword}</td>
                  <td className="px-4 py-3 text-muted-foreground">{rule.response}</td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => onPromoteRule(rule.id)}
                      className="inline-flex items-center gap-1.5 rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 transition-colors"
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
