import { Activity, Gauge, MessageSquareText, PlayCircle, Search } from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import { StatTile } from "../components/ui/StatTile";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from "../components/ui/Table";
import { RevealSection, RevealItem } from "../components/landing/RevealSection";
import { useFeedbackSummary, useRunBenchmark, useSearchAnalytics } from "../hooks/useRagOperations";
import { formatDateTime } from "../lib/utils";

export default function RagOperationsPage() {
  const { data: analytics, isLoading: loadingAnalytics } = useSearchAnalytics();
  const { data: feedback, isLoading: loadingFeedback } = useFeedbackSummary();
  const benchmark = useRunBenchmark();

  return (
    <div>
      <PageHeader
        title="RAG Operations"
        description="Live performance benchmarking, search analytics, and feedback for the knowledge base / AI Assistant / Finding Intelligence / Executive Intelligence pipeline."
      />

      <RevealSection className="mb-6">
        <RevealItem>
          <Card>
            <CardHeader
              title="Benchmark"
              description="Runs a live timing probe (embedding, vector search, rerank, LLM) against the current knowledge base — a performance check, not a quality/relevance check."
              action={
                <Button onClick={() => benchmark.mutate()} isLoading={benchmark.isPending}>
                  <PlayCircle className="size-4" />
                  Run benchmark
                </Button>
              }
            />
            <CardContent>
              {!benchmark.data && !benchmark.isPending && (
                <p className="text-sm text-muted-foreground">Click "Run benchmark" to measure current latency.</p>
              )}
              {benchmark.data && (
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <Badge tone={benchmark.data.llm_configured ? "success" : "warning"}>
                      {benchmark.data.llm_configured ? "LLM provider configured" : "No LLM provider configured"}
                    </Badge>
                    <span>{benchmark.data.documents_indexed} document(s) indexed</span>
                    <span>Ran {formatDateTime(benchmark.data.ran_at)}</span>
                    <span>Total: {benchmark.data.total_duration_ms}ms</span>
                  </div>
                  <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                    {benchmark.data.stages.map((stage) => (
                      <div key={stage.stage} className="rounded-lg border border-border p-3">
                        <p className="text-xs capitalize text-muted-foreground">{stage.stage.replace(/_/g, " ")}</p>
                        <p className="mt-1 text-lg font-semibold tabular-nums">{stage.avg_duration_ms}ms</p>
                        {stage.detail && <p className="mt-0.5 text-xs text-muted-foreground">{stage.detail}</p>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </RevealItem>
      </RevealSection>

      <RevealSection className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <RevealItem>
          <Card className="h-full">
            <CardHeader title="Search analytics" description="Persisted across knowledge search, AI Assistant chat, finding intelligence, and executive ask." />
            <CardContent>
              {loadingAnalytics ? (
                <p className="text-sm text-muted-foreground">Loading…</p>
              ) : !analytics || analytics.total_searches === 0 ? (
                <EmptyState icon={<Search className="size-8" />} title="No searches recorded yet" />
              ) : (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <StatTile label="Total operations" value={analytics.total_searches} icon={<Activity className="size-4" />} />
                    <StatTile
                      label="Avg latency"
                      value={analytics.average_latency_ms != null ? `${analytics.average_latency_ms}ms` : "—"}
                      icon={<Gauge className="size-4" />}
                    />
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Badge tone={analytics.zero_result_rate && analytics.zero_result_rate > 0.3 ? "warning" : "neutral"}>
                      {analytics.zero_result_count} zero-result operations
                      {analytics.zero_result_rate != null && ` (${Math.round(analytics.zero_result_rate * 100)}%)`}
                    </Badge>
                  </div>
                  {analytics.recent_searches.length > 0 && (
                    <Table>
                      <TableHead>
                        <tr>
                          <TableHeaderCell>Feature</TableHeaderCell>
                          <TableHeaderCell>Query</TableHeaderCell>
                          <TableHeaderCell>Results</TableHeaderCell>
                          <TableHeaderCell>Latency</TableHeaderCell>
                        </tr>
                      </TableHead>
                      <TableBody>
                        {analytics.recent_searches.slice(0, 8).map((entry, index) => (
                          <TableRow key={index}>
                            <TableCell className="text-xs">{entry.feature}</TableCell>
                            <TableCell className="max-w-[220px] truncate text-xs">{entry.query}</TableCell>
                            <TableCell className="text-xs tabular-nums">{entry.result_count}</TableCell>
                            <TableCell className="text-xs tabular-nums">{entry.latency_ms}ms</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </RevealItem>

        <RevealItem>
          <Card className="h-full">
            <CardHeader title="Feedback" description="Thumbs up/down submitted by users on AI-generated answers." />
            <CardContent>
              {loadingFeedback ? (
                <p className="text-sm text-muted-foreground">Loading…</p>
              ) : !feedback || feedback.total_feedback === 0 ? (
                <EmptyState icon={<MessageSquareText className="size-8" />} title="No feedback submitted yet" />
              ) : (
                <div className="grid grid-cols-2 gap-3">
                  <StatTile label="Total feedback" value={feedback.total_feedback} />
                  <StatTile
                    label="Positive rate"
                    value={feedback.positive_rate != null ? `${Math.round(feedback.positive_rate * 100)}%` : "—"}
                  />
                  <StatTile label="👍 Positive" value={feedback.positive_count} />
                  <StatTile label="👎 Negative" value={feedback.negative_count} />
                </div>
              )}
            </CardContent>
          </Card>
        </RevealItem>
      </RevealSection>
    </div>
  );
}
