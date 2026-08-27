import { useEffect, useState } from "react";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import { KnowledgeGapInbox } from "../components/knowledge/KnowledgeGapInbox";
import { useToast } from "../hooks/useToast";
import {
  fetchGapInbox,
  fetchKnowledgeEvolutionMetrics,
  promoteGapRule,
  type FAQRuleItem,
} from "../lib/api/faq";
import type { KnowledgeEvolutionMetrics } from "../types/api";

export default function KnowledgeEvolutionPage() {
  const toast = useToast();
  const [draftRules, setDraftRules] = useState<FAQRuleItem[]>([]);
  const [metrics, setMetrics] = useState<KnowledgeEvolutionMetrics | null>(null);

  const loadData = async () => {
    try {
      const [drafts, evoMetrics] = await Promise.all([
        fetchGapInbox(),
        fetchKnowledgeEvolutionMetrics(),
      ]);
      setDraftRules(drafts);
      setMetrics(evoMetrics);
    } catch {
      // quiet fail
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handlePromoteRule = async (id: string) => {
    try {
      await promoteGapRule(id);
      toast.success("FAQ Rule Promoted!", "Converted candidate cluster into an active Stage 0 instant 0ms FAQ rule.");
      await loadData();
    } catch {
      toast.error("Failed to promote gap rule");
    }
  };

  const failureRateDisplay =
    metrics?.failure_refusal_rate != null
      ? `${(metrics.failure_refusal_rate * 100).toFixed(1)}%`
      : "0.0%";

  const stage0RatioDisplay =
    metrics?.stage_0_match_ratio != null
      ? `${(metrics.stage_0_match_ratio * 100).toFixed(1)}%`
      : "0.0%";

  const pendingClustersCount =
    metrics?.pending_gap_candidates_count ?? draftRules.length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Knowledge Evolution & Outer-Loop Self-Healing"
        description="Outer-loop Celery workers density-cluster unhandled retrieval failures using HDBSCAN to auto-synthesize draft FAQ axioms."
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader title="Failure Refusal Rate" description="Unresolved retrieval gap rate" />
          <CardContent>
            <div className="text-2xl font-extrabold text-emerald-400">{failureRateDisplay}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {metrics?.total_queries ? `${metrics.total_queries} queries analyzed` : "No query failures recorded"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader title="HDBSCAN Clusters" description="Synthesized FAQ candidates" />
          <CardContent>
            <div className="text-2xl font-extrabold text-amber-400">{pendingClustersCount} Pending</div>
            <p className="text-xs text-muted-foreground mt-1">
              {metrics ? `${metrics.active_faq_count} active FAQ rules in production` : "Awaiting 1-click administrative promotion"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader title="Stage 0 Match Ratio" description="Sub-millisecond fast hits" />
          <CardContent>
            <div className="text-2xl font-extrabold text-primary">{stage0RatioDisplay}</div>
            <p className="text-xs text-muted-foreground mt-1">Queries served in &lt;1ms at 0 token cost</p>
          </CardContent>
        </Card>
      </div>

      <KnowledgeGapInbox draftRules={draftRules} onPromoteRule={handlePromoteRule} />
    </div>
  );
}
