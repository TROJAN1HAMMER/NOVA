import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import type { FAQRuleItem } from "../../lib/api/faq";

interface FaqManagerProps {
  rules: FAQRuleItem[];
  onCreateRule: (keyword: string, response: string) => Promise<void>;
  onDeleteRule: (id: string) => Promise<void>;
}

export function FaqManager({ rules, onCreateRule, onDeleteRule }: FaqManagerProps) {
  const [keyword, setKeyword] = useState("");
  const [response, setResponse] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!keyword.trim() || !response.trim()) return;
    try {
      setLoading(true);
      await onCreateRule(keyword.trim(), response.trim());
      setKeyword("");
      setResponse("");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <form onSubmit={handleSubmit} className="rounded-xl border border-border bg-card p-4 shadow-sm space-y-4">
        <h3 className="text-sm font-semibold tracking-tight text-foreground">Add Instant FAQ Rule (0ms Routing)</h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1">Trigger Keyword / Phrase</label>
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="e.g. refund policy, reset password"
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1">Instant Response Text</label>
            <input
              type="text"
              value={response}
              onChange={(e) => setResponse(e.target.value)}
              placeholder="Official answer text to return directly..."
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              required
            />
          </div>
        </div>
        <button
          type="submit"
          disabled={loading}
          className="flex items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          <Plus className="size-4" />
          Add FAQ Rule
        </button>
      </form>

      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="px-4 py-3 border-b border-border font-semibold text-sm">Active FAQ Keyword Rules</div>
        <table className="w-full text-left text-sm">
          <thead className="bg-muted/50 text-xs font-medium text-muted-foreground uppercase">
            <tr>
              <th className="px-4 py-2">Keyword</th>
              <th className="px-4 py-2">Response</th>
              <th className="px-4 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rules.length === 0 ? (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center text-xs text-muted-foreground">
                  No custom FAQ rules added yet.
                </td>
              </tr>
            ) : (
              rules.map((rule) => (
                <tr key={rule.id} className="hover:bg-muted/30">
                  <td className="px-4 py-3 font-medium text-foreground">{rule.keyword}</td>
                  <td className="px-4 py-3 text-muted-foreground">{rule.response}</td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => onDeleteRule(rule.id)}
                      className="text-muted-foreground hover:text-destructive transition-colors"
                      title="Delete rule"
                    >
                      <Trash2 className="size-4" />
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
