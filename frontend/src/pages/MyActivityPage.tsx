import { useState } from "react";
import {
  Activity,
  Clock,
  Database,
  Layers,
  Brain,
  Network,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
  FileText,
} from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { StatTile } from "../components/ui/StatTile";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { EmptyState } from "../components/ui/EmptyState";
import {
  SkeletonStatTiles,
  SkeletonChartCard,
  SkeletonTable,
} from "../components/ui/Skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "../components/ui/Table";
import { RevealSection, RevealItem } from "../components/landing/RevealSection";
import { useMyActivity } from "../hooks/useAnalytics";
import { formatDateTime, formatDuration } from "../lib/utils";
import type { KnowledgeJobStatus } from "../types/api";

const STATUS_TONE: Record<
  string,
  "neutral" | "primary" | "success" | "warning" | "danger"
> = {
  queued: "neutral",
  running: "primary",
  completed: "success",
  failed: "danger",
  cancelled: "warning",
};

const STATUS_ICON: Record<string, React.ReactNode> = {
  completed: <CheckCircle2 className="size-3.5 text-emerald-400" />,
  failed: <XCircle className="size-3.5 text-red-400" />,
  running: <Loader2 className="size-3.5 text-primary animate-spin" />,
  queued: <AlertCircle className="size-3.5 text-muted-foreground" />,
  cancelled: <XCircle className="size-3.5 text-amber-400" />,
};



export default function MyActivityPage() {
  const { data, isLoading } = useMyActivity();
  const [_status] = useState<KnowledgeJobStatus | "all">("all");

  if (isLoading) {
    return (
      <div>
        <PageHeader
          title="My Knowledge Activity"
          description="Your personal knowledge ingestion history, processing metrics, and pipeline outcomes."
        />
        <SkeletonStatTiles className="mb-6" />
        <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <SkeletonChartCard height={220} />
          <SkeletonChartCard height={220} />
        </div>
        <SkeletonTable rows={5} columns={5} />
      </div>
    );
  }

  if (!data || data.total_scans === 0) {
    return (
      <div>
        <PageHeader
          title="My Knowledge Activity"
          description="Your personal knowledge ingestion history, processing metrics, and pipeline outcomes."
        />
        <EmptyState
          icon={<Brain className="size-10" />}
          title="No knowledge operations yet"
          description="Once you start ingesting knowledge sources, your activity will appear here."
        />
      </div>
    );
  }

  const statusEntries = Object.entries(data.scans_by_status ?? {});

  return (
    <div>
      <PageHeader
        title="My Knowledge Activity"
        description="Your personal knowledge ingestion history, processing metrics, and pipeline outcomes."
      />

      {/* Stat Tiles */}
      <RevealSection className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <RevealItem>
          <StatTile
            label="Knowledge Operations"
            value={data.total_scans}
            icon={<Activity className="size-5" />}
          />
        </RevealItem>
        <RevealItem>
          <StatTile
            label="Documents Processed"
            value={data.total_findings}
            icon={<Database className="size-5" />}
          />
        </RevealItem>
        <RevealItem>
          <StatTile
            label="Avg Confidence Score"
            value={
              data.average_brs_score != null
                ? `${data.average_brs_score.toFixed(1)}%`
                : "—"
            }
            icon={<Brain className="size-5" />}
          />
        </RevealItem>
        <RevealItem>
          <StatTile
            label="Avg Processing Time"
            value={formatDuration(data.average_scan_duration_seconds)}
            icon={<Clock className="size-5" />}
          />
        </RevealItem>
      </RevealSection>

      {/* Status Breakdown + Pipeline Metrics */}
      <RevealSection className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <RevealItem>
          <Card className="h-full">
            <CardHeader title="Knowledge Jobs by Status" />
            <CardContent className="flex flex-wrap gap-2">
              {statusEntries.length === 0 ? (
                <p className="text-sm text-muted-foreground">No jobs yet.</p>
              ) : (
                statusEntries.map(([status, count]) => (
                  <Badge
                    key={status}
                    tone={STATUS_TONE[status] ?? "neutral"}
                    className="capitalize flex items-center gap-1.5"
                  >
                    {STATUS_ICON[status]}
                    {status}: {String(count)}
                  </Badge>
                ))
              )}
            </CardContent>
          </Card>
        </RevealItem>

        <RevealItem>
          <Card className="h-full">
            <CardHeader
              title="Pipeline Throughput"
              description="Cumulative output from all your ingestion runs"
            />
            <CardContent className="grid grid-cols-2 gap-4">
              <div className="flex flex-col gap-1">
                <Layers className="size-5 text-cyan-400" />
                <div className="text-2xl font-extrabold text-foreground">
                  {data.total_scans}
                </div>
                <div className="text-xs text-muted-foreground">
                  Processed Queries
                </div>
              </div>
              <div className="flex flex-col gap-1">
                <Network className="size-5 text-primary" />
                <div className="text-2xl font-extrabold text-foreground">
                  {data.total_findings}
                </div>
                <div className="text-xs text-muted-foreground">
                  Indexed Documents
                </div>
              </div>
            </CardContent>
          </Card>
        </RevealItem>
      </RevealSection>

      {/* Recent Operations Table */}
      <RevealSection>
        <RevealItem>
          <Card>
            <CardHeader title="Recent Knowledge Operations" />
            <Table>
              <TableHead>
                <tr>
                  <TableHeaderCell>Source</TableHeaderCell>
                  <TableHeaderCell>Status</TableHeaderCell>
                  <TableHeaderCell>Risk Level</TableHeaderCell>
                  <TableHeaderCell>BRS Score</TableHeaderCell>
                  <TableHeaderCell>Completed</TableHeaderCell>
                </tr>
              </TableHead>
              <TableBody>
                {(data.recent_scans ?? []).map((op) => (
                  <TableRow key={op.scan_job_id}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        <FileText className="size-4 text-primary shrink-0" />
                        <span className="truncate max-w-xs">
                          {op.repository_name || "—"}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge
                        tone={STATUS_TONE[op.status] ?? "neutral"}
                        className="capitalize flex items-center gap-1"
                      >
                        {STATUS_ICON[op.status]}
                        {op.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="tabular-nums text-xs text-primary">
                      {op.brs_risk_level ?? "—"}
                    </TableCell>
                    <TableCell className="tabular-nums text-xs text-cyan-400">
                      {op.brs_score != null ? op.brs_score.toFixed(1) : "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-xs">
                      {formatDateTime(op.finished_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </RevealItem>
      </RevealSection>
    </div>
  );
}
