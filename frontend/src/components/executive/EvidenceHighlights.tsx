import { Minus, TrendingDown, TrendingUp } from "lucide-react";
import { RadialGauge } from "../charts/RadialGauge";
import { Badge } from "../ui/Badge";
import { useChartTheme } from "../../hooks/useChartTheme";
import { confidenceTier, CONFIDENCE_STYLES } from "../../lib/severity";
import { cn } from "../../lib/utils";
import type { ExecutiveEvidenceSnapshot } from "../../types/api";

function ConfidenceCountBadge({ tier, count }: { tier: string; count: number }) {
  const style = CONFIDENCE_STYLES[tier as keyof typeof CONFIDENCE_STYLES] ?? CONFIDENCE_STYLES.UNCERTAIN;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset",
        style.bg,
        style.text,
        style.ring,
      )}
    >
      <span className={cn("size-1.5 rounded-full", style.dot)} />
      {style.label}: {count}
    </span>
  );
}

function ConfidenceTrendIndicator({
  current,
  previous,
}: {
  current: number | null;
  previous: number | null;
}) {
  if (current === null || previous === null) return null;
  const delta = (current - previous) * 100;
  if (Math.abs(delta) < 0.5) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
        <Minus className="size-3.5" />
        Flat vs. last week
      </span>
    );
  }
  // Higher confidence is better — rising = good
  const isRising = delta > 0;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-xs font-medium",
        isRising ? "text-emerald-400" : "text-danger",
      )}
    >
      {isRising ? <TrendingUp className="size-3.5" /> : <TrendingDown className="size-3.5" />}
      {isRising ? "+" : ""}
      {delta.toFixed(1)}% vs. last week
    </span>
  );
}

/**
 * Renders a rich summary of the ExecutiveEvidenceSnapshot used by the
 * AI Intelligence panel. Shows NOVA-native confidence metrics, knowledge
 * source health, and week-over-week deltas — no BRS/risk/compliance data.
 */
export function EvidenceHighlights({ evidence }: { evidence: ExecutiveEvidenceSnapshot }) {
  const chartTheme = useChartTheme();

  const totalOps = evidence.total_completed_scans;
  const totalSources = evidence.total_repositories;

  if (totalOps === 0 && totalSources === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No knowledge operations completed yet.
      </p>
    );
  }

  const confidence = evidence.portfolio_average_brs != null ? evidence.portfolio_average_brs / 100 : null;
  const tier = confidenceTier(confidence);
  const confidenceValue = confidence != null ? confidence * 100 : null;

  const wow = evidence.week_over_week;

  return (
    <div className="space-y-4 rounded-lg border border-border bg-muted/30 p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Evidence corpus ({totalOps} operations · {totalSources} knowledge sources)
      </p>

      <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center sm:gap-6">
        <div className="flex shrink-0 flex-col items-center gap-1">
          <RadialGauge
            label="Avg confidence"
            value={confidenceValue}
            mode={chartTheme.mode}
            size={136}
          />
          {wow && (
            <ConfidenceTrendIndicator
              current={wow.average_brs_this_week != null ? wow.average_brs_this_week / 100 : null}
              previous={wow.average_brs_last_week != null ? wow.average_brs_last_week / 100 : null}
            />
          )}
        </div>

        <div className="grid w-full grid-cols-2 gap-3 sm:w-auto sm:flex-1 sm:grid-cols-3">
          <div>
            <p className="text-xs text-muted-foreground">Documents indexed</p>
            <p className="text-lg font-semibold tabular-nums">
              {totalSources}
            </p>
          </div>
          {wow && (
            <>
              <div>
                <p className="text-xs text-muted-foreground">Operations this week</p>
                <p className="text-lg font-semibold tabular-nums">
                  {wow.scans_this_week}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">vs. last week</p>
                <p className="text-lg font-semibold tabular-nums">
                  {wow.scans_last_week}
                </p>
              </div>
            </>
          )}
        </div>
      </div>

      <ConfidenceCountBadge tier={tier} count={totalOps} />

      {(evidence.top_risk_repositories ?? []).length > 0 && (
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">Top knowledge sources</p>
          <div className="flex flex-wrap gap-1.5">
            {(evidence.top_risk_repositories ?? [])
              .slice(0, 5)
              .map((src, i) => (
                <Badge
                  key={src.repository_id ?? i}
                  tone={
                    src.latest_brs_score >= 80
                      ? "success"
                      : src.latest_brs_score >= 50
                      ? "warning"
                      : "danger"
                  }
                >
                  {src.repository_name}
                </Badge>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
