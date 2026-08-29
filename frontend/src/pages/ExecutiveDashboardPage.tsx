import { useMemo } from "react";
import {
  BarChart3,
  Brain,
  Database,
  FileText,
  Layers,
  Network,
  TrendingUp,
  Zap,
} from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { StatTile } from "../components/ui/StatTile";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { SkeletonStatTiles, SkeletonChartCard } from "../components/ui/Skeleton";
import { EmptyState } from "../components/ui/EmptyState";
import { RevealSection, RevealItem } from "../components/landing/RevealSection";
import { ExecutiveIntelligencePanel } from "../components/executive/ExecutiveIntelligencePanel";
import { useKnowledgeDocuments } from "../hooks/useKnowledge";
import { useMyActivity } from "../hooks/useAnalytics";
import type { KnowledgeDocument, WeekOverWeekDelta, WeeklyTrendPoint } from "../types/api";

function confidenceBadge(score: number | null): { tone: "success" | "warning" | "danger" | "neutral"; label: string } {
  if (score == null) return { tone: "neutral", label: "No data" };
  if (score >= 0.85) return { tone: "success", label: "High Confidence" };
  if (score >= 0.65) return { tone: "warning", label: "Moderate Confidence" };
  return { tone: "danger", label: "Low Confidence" };
}

interface ExecutiveSummary {
  totalSources: number;
  totalDocuments: number;
  totalOperations: number;
  totalChunks: number;
  confidence: number | null;
  topSources: KnowledgeDocument[];
  weeklyTrend: WeeklyTrendPoint[];
  weekOverWeek: WeekOverWeekDelta | null;
}

export default function ExecutiveDashboardPage() {
  const { data: docsData, isLoading: docsLoading } = useKnowledgeDocuments({ limit: 200 });
  const { data: activityData, isLoading: activityLoading } = useMyActivity();

  const isLoading = docsLoading || activityLoading;

  const summary: ExecutiveSummary = useMemo(() => {
    const docs = docsData?.documents ?? [];
    const indexed = docs.filter((d) => ["indexed", "ready", "processed"].includes((d.status ?? "").toLowerCase()));
    const totalChunks = indexed.reduce((sum, d) => sum + (d.chunk_count ?? 0), 0);

    return {
      totalSources: docsData?.total ?? docs.length,
      totalDocuments: indexed.length,
      totalOperations: activityData?.total_scans ?? 0,
      totalChunks,
      confidence: activityData?.average_brs_score != null ? activityData.average_brs_score / 100 : null,
      topSources: indexed.slice(0, 5),
      weeklyTrend: [],
      weekOverWeek: null,
    };
  }, [docsData, activityData]);

  if (isLoading) {
    return (
      <div>
        <PageHeader
          title="Executive Intelligence"
          description="Portfolio-level knowledge health, retrieval confidence, and AI usage insights for leadership."
        />
        <SkeletonStatTiles className="mb-6" count={4} />
        <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <SkeletonChartCard />
          <SkeletonChartCard />
        </div>
      </div>
    );
  }

  if (summary.totalSources === 0 && summary.totalDocuments === 0) {
    return (
      <div>
        <PageHeader
          title="Executive Intelligence"
          description="Portfolio-level knowledge health, retrieval confidence, and AI usage insights for leadership."
        />
        <EmptyState
          icon={<BarChart3 className="size-10" />}
          title="No knowledge data yet"
          description="Once knowledge has been ingested and the assistant has been used, executive insights will appear here."
        />
      </div>
    );
  }

  const confidenceInfo = confidenceBadge(summary.confidence);
  const wow = summary.weekOverWeek;

  return (
    <div>
      <PageHeader
        title="Executive Intelligence"
        description="Portfolio-level knowledge health, retrieval confidence, and AI usage insights for leadership."
      />

      {/* Top-line KPIs */}
      <RevealSection className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <RevealItem>
          <StatTile
            label="Knowledge Sources"
            value={summary.totalSources}
            icon={<Database className="size-5" />}
          />
        </RevealItem>
        <RevealItem>
          <StatTile
            label="Knowledge Operations"
            value={summary.totalOperations}
            icon={<Zap className="size-5" />}
          />
        </RevealItem>
        <RevealItem>
          <StatTile
            label="Documents Indexed"
            value={summary.totalDocuments}
            icon={<FileText className="size-5" />}
          />
        </RevealItem>
        <RevealItem>
          <StatTile
            label="Vector Chunks"
            value={summary.totalChunks}
            icon={<Layers className="size-5" />}
          />
        </RevealItem>
      </RevealSection>

      {/* Confidence Banner */}
      <RevealSection className="mb-6">
        <RevealItem>
          <Card>
            <CardContent className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <Brain className="size-8 text-primary" />
                <div>
                  <div className="flex items-center gap-2">
                    <Badge tone={confidenceInfo.tone}>{confidenceInfo.label}</Badge>
                    <span className="text-sm text-muted-foreground">
                      Portfolio avg confidence:{" "}
                      {summary.confidence != null
                        ? `${(summary.confidence * 100).toFixed(1)}%`
                        : "—"}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Average AEKOF retrieval confidence across all assistant interactions.
                  </p>
                </div>
              </div>
              {wow && (
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <span>
                    This week:{" "}
                    <strong className="text-foreground">
                      {wow.scans_this_week} ops
                    </strong>
                  </span>
                  <span>
                    Last week:{" "}
                    <strong className="text-foreground">
                      {wow.scans_last_week} ops
                    </strong>
                  </span>
                </div>
              )}
            </CardContent>
          </Card>
        </RevealItem>
      </RevealSection>

      {/* Top Sources + Entity Graph */}
      <RevealSection className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <RevealItem>
          <Card className="h-full">
            <CardHeader
              title="Top Knowledge Sources"
              description="Highest-contributing sources by indexed chunk volume."
            />
            <CardContent>
              <ul className="space-y-3">
                {summary.topSources.slice(0, 5).map((src, i) => (
                  <li key={src.id ?? i} className="flex items-center justify-between gap-2 text-sm">
                    <div className="flex items-center gap-2 min-w-0">
                      <FileText className="size-4 text-primary shrink-0" />
                      <span className="truncate font-medium text-foreground">
                        {src.filename}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-xs text-muted-foreground">
                        {src.chunk_count ?? 0} chunks
                      </span>
                      <Badge tone="success">
                        Indexed
                      </Badge>
                    </div>
                  </li>
                ))}
                {summary.topSources.length === 0 && (
                  <p className="text-sm text-muted-foreground">No sources indexed yet.</p>
                )}
              </ul>
            </CardContent>
          </Card>
        </RevealItem>

        <RevealItem>
          <Card className="h-full">
            <CardHeader
              title="Knowledge Graph Summary"
              description="Entities and relationships extracted from the knowledge corpus."
            />
            <CardContent className="grid grid-cols-2 gap-6">
              <div className="flex flex-col gap-1">
                <Network className="size-6 text-primary" />
                <div className="text-3xl font-extrabold text-foreground">{summary.totalDocuments}</div>
                <div className="text-xs text-muted-foreground">Indexed Documents</div>
              </div>
              <div className="flex flex-col gap-1">
                <TrendingUp className="size-6 text-cyan-400" />
                <div className="text-3xl font-extrabold text-foreground">{summary.totalChunks}</div>
                <div className="text-xs text-muted-foreground">Indexed Chunks</div>
              </div>
            </CardContent>
          </Card>
        </RevealItem>
      </RevealSection>

      {/* Weekly Trend */}
      {summary.weeklyTrend.length > 0 && (
        <RevealSection className="mb-6">
          <RevealItem>
            <Card>
              <CardHeader title="Weekly Knowledge Trend" description="Operations and documents indexed per week." />
              <CardContent>
                <div className="flex gap-4 overflow-x-auto pb-1">
                  {summary.weeklyTrend.map((pt) => (
                    <div key={pt.week_start} className="flex flex-col items-center gap-1 min-w-[72px]">
                      <div className="w-10 rounded-t-md bg-primary/60" style={{ height: `${Math.min(80, pt.scan_count * 8)}px`, minHeight: "4px" }} />
                      <span className="text-[10px] text-muted-foreground">{pt.week_start.slice(5)}</span>
                      <span className="text-xs font-semibold">{pt.scan_count}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </RevealItem>
        </RevealSection>
      )}

      {/* AI Intelligence Panel */}
      <RevealSection>
        <RevealItem>
          <ExecutiveIntelligencePanel />
        </RevealItem>
      </RevealSection>
    </div>
  );
}
