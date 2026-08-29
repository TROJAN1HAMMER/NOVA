import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  Gauge,
  MessageSquareText,
  PlayCircle,
  Search,
  Zap,
  AlertTriangle,
  Cpu,
  ThumbsUp,
  ThumbsDown,
} from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, CardContent, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { Table, TableBody, TableCell, TableHead, TableHeaderCell } from "../components/ui/Table";
import { useFeedbackSummary, useRunBenchmark, useSearchAnalytics } from "../hooks/useRagOperations";
import { formatDateTime } from "../lib/utils";

export default function RagOperationsPage() {
  const { data: analytics, isLoading: loadingAnalytics } = useSearchAnalytics();
  const { data: feedback, isLoading: loadingFeedback } = useFeedbackSummary();
  const benchmark = useRunBenchmark();

  const [queryFilter, setQueryFilter] = useState("");
  const [selectedFeature, setSelectedFeature] = useState("all");

  const filteredSearches = useMemo(() => {
    if (!analytics?.recent_searches) return [];
    return analytics.recent_searches.filter((entry) => {
      const matchesText = entry.query.toLowerCase().includes(queryFilter.toLowerCase());
      const matchesFeature = selectedFeature === "all" || entry.feature === selectedFeature;
      return matchesText && matchesFeature;
    });
  }, [analytics, queryFilter, selectedFeature]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="RAG Studio & Pipeline Telemetry"
        description="Real-time performance benchmarking, search analytics, zero-result self-healing gap tracking, and user feedback."
      />

      {/* Top Animated Summary Stat Bar */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="grid grid-cols-1 gap-4 sm:grid-cols-4"
      >
        <Card className="relative overflow-hidden p-4 bg-gradient-to-br from-primary/15 via-card to-card border-primary/30">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
            <span className="flex items-center gap-1.5 font-medium text-foreground">
              <Activity className="size-4 text-primary" /> Total Operations
            </span>
            <Badge tone="primary">Live Telemetry</Badge>
          </div>
          <div className="text-3xl font-bold text-foreground font-mono">
            {analytics?.total_searches ?? 0}
          </div>
          <div className="text-[11px] text-muted-foreground mt-1">Queries across all features</div>
        </Card>

        <Card className="relative overflow-hidden p-4 bg-gradient-to-br from-cyan-500/15 via-card to-card border-cyan-500/30">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
            <span className="flex items-center gap-1.5 font-medium text-foreground">
              <Gauge className="size-4 text-cyan-400" /> Average Latency
            </span>
            <Badge tone="success">&lt;100ms Target</Badge>
          </div>
          <div className="text-3xl font-bold text-cyan-400 font-mono">
            {analytics?.average_latency_ms != null ? `${analytics.average_latency_ms} ms` : "—"}
          </div>
          <div className="text-[11px] text-muted-foreground mt-1">End-to-end response time</div>
        </Card>

        <Card className="relative overflow-hidden p-4 bg-gradient-to-br from-amber-500/15 via-card to-card border-amber-500/30">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
            <span className="flex items-center gap-1.5 font-medium text-foreground">
              <AlertTriangle className="size-4 text-amber-400" /> Zero-Result Gaps
            </span>
            <Badge tone={analytics?.zero_result_count ? "warning" : "success"}>
              {analytics?.zero_result_rate ? `${Math.round(analytics.zero_result_rate * 100)}%` : "0%"}
            </Badge>
          </div>
          <div className="text-3xl font-bold text-amber-400 font-mono">
            {analytics?.zero_result_count ?? 0}
          </div>
          <div className="text-[11px] text-muted-foreground mt-1">Gaps routed to Self-Healing Inbox</div>
        </Card>

        <Card className="relative overflow-hidden p-4 bg-gradient-to-br from-emerald-500/15 via-card to-card border-emerald-500/30">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
            <span className="flex items-center gap-1.5 font-medium text-foreground">
              <ThumbsUp className="size-4 text-emerald-400" /> User Satisfaction
            </span>
            <Badge tone="success">100% Positive</Badge>
          </div>
          <div className="text-3xl font-bold text-emerald-400 font-mono">
            {feedback?.positive_rate != null ? `${Math.round(feedback.positive_rate * 100)}%` : "100%"}
          </div>
          <div className="text-[11px] text-muted-foreground mt-1">
            {feedback?.total_feedback ?? 0} rating(s) submitted
          </div>
        </Card>
      </motion.div>

      {/* Benchmark Probe Card */}
      <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: 0.1 }}>
        <Card className="border-primary/40 bg-gradient-to-r from-card via-background to-card shadow-lg">
          <CardHeader
            title="Live Pipeline Benchmark Probe"
            description="Executes a real-time 4-stage timing probe against active embedding, vector store, reranker, and LLM gateway."
            action={
              <Button onClick={() => benchmark.mutate()} isLoading={benchmark.isPending} className="gap-2">
                <PlayCircle className={`size-4 ${benchmark.isPending ? "animate-spin" : ""}`} />
                {benchmark.isPending ? "Executing Probe…" : "Run Benchmark"}
              </Button>
            }
          />
          <CardContent>
            {!benchmark.data && !benchmark.isPending && (
              <div className="p-4 rounded-lg bg-muted/20 border border-border/40 text-xs text-muted-foreground flex items-center gap-2">
                <Zap className="size-4 text-primary animate-pulse" />
                Click <strong>"Run benchmark"</strong> to measure active pipeline latency across indexed documents.
              </div>
            )}
            {benchmark.data && (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                  <Badge tone={benchmark.data.llm_configured ? "success" : "warning"}>
                    {benchmark.data.llm_configured ? "LLM Gateway Connected" : "No LLM Provider Configured"}
                  </Badge>
                  <span>•</span>
                  <span>{benchmark.data.documents_indexed} document(s) indexed</span>
                  <span>•</span>
                  <span>Ran {formatDateTime(benchmark.data.ran_at)}</span>
                  <span>•</span>
                  <span className="font-mono font-bold text-foreground">Total: {benchmark.data.total_duration_ms}ms</span>
                </div>

                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {benchmark.data.stages.map((stage, idx) => {
                    const colors = [
                      "from-blue-500/20 to-cyan-500/10 border-blue-500/30",
                      "from-cyan-500/20 to-teal-500/10 border-cyan-500/30",
                      "from-indigo-500/20 to-purple-500/10 border-indigo-500/30",
                      "from-emerald-500/20 to-lime-500/10 border-emerald-500/30",
                    ];
                    return (
                      <motion.div
                        key={stage.stage}
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ duration: 0.2, delay: idx * 0.05 }}
                        className={`rounded-lg border p-3.5 bg-gradient-to-br ${colors[idx % colors.length]} hover:scale-[1.02] transition-all`}
                      >
                        <p className="text-xs capitalize text-muted-foreground flex items-center gap-1.5 font-medium">
                          <Cpu className="size-3.5 text-primary" />
                          {stage.stage.replace(/_/g, " ")}
                        </p>
                        <p className="mt-1 text-xl font-bold text-foreground font-mono tabular-nums">
                          {stage.avg_duration_ms} ms
                        </p>
                        {stage.detail && (
                          <p className="mt-1 text-[11px] text-muted-foreground truncate" title={stage.detail}>
                            {stage.detail}
                          </p>
                        )}
                      </motion.div>
                    );
                  })}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>

      {/* Main Grid: Search Telemetry & Feedback */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-4">
          <Card className="h-full">
            <CardHeader
              title="Search Analytics Telemetry"
              description="Persisted query performance logs across Knowledge Base, AI Assistant, Finding Intelligence, and Executive Intelligence."
              action={
                <div className="flex flex-wrap items-center gap-2">
                  <div className="relative">
                    <Search className="absolute left-2.5 top-2 size-3.5 text-muted-foreground" />
                    <input
                      type="text"
                      value={queryFilter}
                      onChange={(e) => setQueryFilter(e.target.value)}
                      placeholder="Filter queries..."
                      className="w-36 sm:w-48 rounded-md border border-border bg-background pl-8 pr-2.5 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
                    />
                  </div>
                  <button
                    onClick={() => setSelectedFeature("all")}
                    className={`px-2 py-1 text-xs rounded border transition-all ${
                      selectedFeature === "all" ? "bg-primary/20 border-primary text-primary font-semibold" : "border-border/40 text-muted-foreground hover:bg-muted/30"
                    }`}
                  >
                    All
                  </button>
                </div>
              }
            />
            <CardContent className="p-0 overflow-x-auto">
              {loadingAnalytics ? (
                <div className="p-6 text-xs text-muted-foreground">Loading telemetry logs…</div>
              ) : !analytics || analytics.total_searches === 0 ? (
                <div className="p-6">
                  <EmptyState icon={<Search className="size-8" />} title="No searches recorded yet" />
                </div>
              ) : (
                <Table>
                  <TableHead>
                    <tr>
                      <TableHeaderCell>Feature Scope</TableHeaderCell>
                      <TableHeaderCell>Query Text</TableHeaderCell>
                      <TableHeaderCell>Results Count</TableHeaderCell>
                      <TableHeaderCell>Latency</TableHeaderCell>
                    </tr>
                  </TableHead>
                  <TableBody>
                    {filteredSearches.slice(0, 10).map((entry, index) => (
                      <motion.tr
                        key={index}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.15, delay: index * 0.02 }}
                        className="hover:bg-muted/30 transition-colors"
                      >
                        <TableCell className="text-xs font-mono text-primary font-medium">{entry.feature}</TableCell>
                        <TableCell className="max-w-[240px] truncate text-xs text-foreground font-medium">{entry.query}</TableCell>
                        <TableCell className="text-xs tabular-nums">
                          <Badge tone={entry.result_count > 0 ? "success" : "warning"}>
                            {entry.result_count} {entry.result_count === 1 ? "match" : "matches"}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs tabular-nums font-mono text-foreground font-semibold">
                          {entry.latency_ms} ms
                        </TableCell>
                      </motion.tr>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: User Feedback Panel */}
        <div>
          <Card className="h-full border-primary/30">
            <CardHeader title="User Answer Feedback" description="Reinforcement ratings submitted on AI responses." />
            <CardContent className="space-y-4">
              {loadingFeedback ? (
                <div className="text-xs text-muted-foreground">Loading feedback summary…</div>
              ) : !feedback || feedback.total_feedback === 0 ? (
                <div className="p-4 rounded-lg bg-muted/20 border border-border/40 text-center space-y-2">
                  <MessageSquareText className="size-8 text-primary mx-auto" />
                  <div className="text-xs font-semibold text-foreground">No Feedback Submitted Yet</div>
                  <p className="text-[11px] text-muted-foreground">
                    Thumbs up/down ratings submitted on AI Assistant messages will appear here.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-center">
                    <div className="text-3xl font-bold text-emerald-400 font-mono">
                      {feedback.positive_rate != null ? `${Math.round(feedback.positive_rate * 100)}%` : "100%"}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">Positive Satisfaction Rate</div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="p-3 rounded-lg bg-muted/30 border border-border/40 flex items-center justify-between">
                      <span className="flex items-center gap-1.5 font-medium">
                        <ThumbsUp className="size-3.5 text-emerald-400" /> Positive
                      </span>
                      <span className="font-mono font-bold text-foreground">{feedback.positive_count}</span>
                    </div>

                    <div className="p-3 rounded-lg bg-muted/30 border border-border/40 flex items-center justify-between">
                      <span className="flex items-center gap-1.5 font-medium">
                        <ThumbsDown className="size-3.5 text-danger" /> Negative
                      </span>
                      <span className="font-mono font-bold text-foreground">{feedback.negative_count}</span>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
